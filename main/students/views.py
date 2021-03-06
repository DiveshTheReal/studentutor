from django.shortcuts import render,redirect

from .forms import StudentSignupForm, StudentProfile, PostAnAdForm, AboutStudentForm, ProfilePicture
from django.contrib.auth.models import Group


from django.contrib.auth.models import User
from django.views.generic import RedirectView

from .decorators import unauthenticated_user, allowed_users, admin_only
from django.contrib.auth.decorators import login_required

from .models import TutorInvitaions , Student, PostAnAd, WishList, WishList_std

from tutors.models import PostAnAd as PostAnAd_tutor
from tutors.models import Invitaions,WishList_tut

from django.contrib import messages

from django.core.mail import EmailMessage
from django.conf import settings
from django.template.loader import render_to_string

from django.contrib.sites.shortcuts import get_current_site
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_text, DjangoUnicodeDecodeError
from .utils import generate_token

from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

import threading
# Create your views here.


def studentRegister(request):
    form = StudentSignupForm()

    if request.method == "POST":
        form = StudentSignupForm(request.POST)

        if form.is_valid():
            student = form.save()
            username = form.cleaned_data.get('username')
            email = form.cleaned_data.get('email')
            age = form.cleaned_data.get('age')
            city = form.cleaned_data.get('city')
            firstName = form.cleaned_data.get('first_name')
            lastName = form.cleaned_data.get('last_name')
            phone = form.cleaned_data.get("phone")

            group = Group.objects.get(name="students")
            student.groups.add(group)

            Student.objects.create(
                student=student,
                username= username,
                email = email,
                age =age,
                city = city,
                first_name = firstName,
                last_name = lastName,
                phone = phone
            )

            student.is_active = False
            student.save()

            current_site = get_current_site(request)

            template = render_to_string("students/activate.html", {
                "firstname": firstName,
                "lastname": lastName,
                "domain": current_site,
                "uid": urlsafe_base64_encode(force_bytes(student.pk)),
                "token": generate_token.make_token(student)
            })
            registerEmail = EmailMessage(
                'Account Activation',
                template,
                settings.EMAIL_HOST_USER,
                [email]
            )
            registerEmail.fail_silently = False
            registerEmail.send()

            return render(request,"students/activation_sent.html",{})

    context = {
        "form": form
    }
    return render(request, 'students/student_sign_up.html', context)


def activate_view(request, uidb64, token):
    try:
        uid = force_text(urlsafe_base64_decode(uidb64))
        student = User.objects.get(pk = uid)
    except:
        student = None

    if student is not None and generate_token.check_token(student, token):
        student.is_active = True
        student.save()

        template = render_to_string("home/registerEmail.html", {
            "firstname": student.first_name,
            "lastname": student.last_name,
            "register_as" : "student"
        })
        registerEmail = EmailMessage(
            'Registration Successful',
            template,
            settings.EMAIL_HOST_USER,
            [student.email]
        )
        registerEmail.fail_silently = False
        registerEmail.send()

        messages.success(request,'account was created for ' + student.username)
        return redirect("sign_in")
    return render(request, 'students/activate_failed.html', status=401)

@login_required(login_url="sign_in")
@allowed_users(allowed_roles=["students"])
def studentDashboard(request):
    student = request.user.student


    form = StudentProfile(instance=student)

    user = Student.objects.get(username = request.user.username)

    active_ads = PostAnAd.objects.filter(studentUser = request.user.student).count()

    p_form = ProfilePicture()

    if request.method=="POST":
        form = StudentProfile(request.POST,request.FILES, instance=student)
        p_form = ProfilePicture(request.POST, request.FILES)

        if p_form.is_valid():
            image = p_form.cleaned_data["image"]
            std_image = Student.objects.get(username = request.user.username)
            std_image.user_image = image
            std_image.save()

            return redirect("student_dashboard")
        else:
            messages.warning(request, 'Supported File Extensions are .jpg And .png, Max Image Size Is 1MB')
            return redirect("student_dashboard")

        if form.is_valid():
            form.save()

    context = {
        "form": form,
        "p_form": p_form,
        "totalAds": user.total_ads,
        "adsDel": user.ads_deleted,
        "activeAds": active_ads,
        "invitations_sent": user.invitations_sent,
        "invitations_sent_accepted": user.invitations_sent_accepted,
        "invitations_sent_rejected": user.invitations_sent_rejected,
        "invitations_recieved": user.invitations_recieved,
        "invitations_recieved_accepted": user.invitations_recieved_accepted,
        "invitations_recieved_rejected": user.invitations_recieved_rejected,
    }
    return render(request, 'students/student_dashboard.html', context)


def post_ad(subject,tuition_level,tuition_type,address,hours_per_day,days_per_week,estimated_fees,user,tutor_gender):
    myad = PostAnAd(
        studentUser = user,
        subject = subject,
        tuition_level = tuition_level,
        tuition_type = tuition_type,
        address = address,
        hours_per_day = hours_per_day,
        days_per_week = days_per_week,
        estimated_fees = estimated_fees,
        tutor_gender = tutor_gender
    )
    myad.save()
    user.total_ads += 1
    user.ad_post_count += 1
    user.save()

def email_send(user,my_ad,emails):
    if emails:
        template = render_to_string("home/stdAD.html", {
            "firstname": user.first_name,
            "lastname": user.last_name,
            "ad":my_ad
            })
        ADEmail = EmailMessage(
            subject = f'{user.first_name} {user.last_name} posted an AD',
            body = template,
            from_email = settings.EMAIL_HOST_USER,
            bcc = emails
        )
        ADEmail.fail_silently = False
        ADEmail.send()

@login_required(login_url="sign_in")
@allowed_users(allowed_roles=["students"])
def postAd(request, pk):
    postform = PostAnAdForm()
    user = Student.objects.get(username = request.user.username)


    studentAds = PostAnAd.objects.filter(studentUser__username = request.user.username)
    wishlist,created = WishList_tut.objects.get_or_create(student=request.user.student)
    emails = []
    tutors = wishlist.tutors.all()
    for t in tutors:
        emails.append(t.email)

    if request.method == "POST":
        postform = PostAnAdForm(request.POST)


        if postform.is_valid():
            subject = postform.cleaned_data["subject"]
            tuition_level = postform.cleaned_data["tuition_level"]
            tuition_type = postform.cleaned_data["tuition_type"]
            tutor_gender = postform.cleaned_data["tutor_gender"]
            address = postform.cleaned_data["address"]
            hours_per_day = postform.cleaned_data["hours_per_day"]
            days_per_week = postform.cleaned_data["days_per_week"]
            estimated_fees = postform.cleaned_data["estimated_fees"]

            adAvailabel = False

            for ad in studentAds:
                if ad.subject == subject and ad.tuition_level == tuition_level:
                    adAvailabel = True
            if adAvailabel == False:
                currentad = {
                    "subject" : subject,
                    "tuition_level" : tuition_level,
                    "tuition_type" : tuition_type,
                    "address" : address,
                    "hours_per_day" : hours_per_day,
                    "days_per_week" : days_per_week,
                    "estimated_fees" : estimated_fees,
                    "tutor_gender":tutor_gender
                }
                my_ad = threading.Thread(target=post_ad, args=[subject,tuition_level,tuition_type,address,hours_per_day,days_per_week,estimated_fees,user,tutor_gender])

                t2 = threading.Thread(target=email_send, args=[user,currentad,emails])

                my_ad.start()
                t2.start()

                messages.info(request, "Your post is Successfully Created")
                return redirect("student_dashboard")
            else:
                messages.info(request, "This AD Already Exists")
                return redirect("student_dashboard")
    context = {
        "form": postform
    }
    return render(request, 'students/post_ad.html', context)



@login_required(login_url="sign_in")
@allowed_users(allowed_roles=["students"])
def Ads(request):
    try:
        studentAbout = AboutStudent.objects.get(student__username = request.user.username).order_by("-id")
    except:
        studentAbout = None
    ads = PostAnAd.objects.filter(studentUser=request.user.student).order_by("-id")
    context = {
        "ads":ads,
        "about": studentAbout
    }
    return render(request, 'students/ads.html', context)

@login_required(login_url="sign_in")
@allowed_users(allowed_roles=["students"])
def AdsDelete(request, pk):

    ad = PostAnAd.objects.get(id=pk)

    user = Student.objects.get(username=request.user.username)

    if request.method == "POST":
        ad.delete()
        user.ads_deleted += 1
        user.ad_post_count -=1
        user.save()
        return redirect("ads")
    context = {
        'ad':ad
    }
    return render(request, 'students/delete_ad.html', context)

@login_required(login_url="sign_in")
@allowed_users(allowed_roles=["students"])
def allTutors(request):
    tutors = PostAnAd_tutor.objects.all().order_by("-id")
    tuition_level_contains_query = request.GET.get('TuitionLevel')
    subject_contains_query = request.GET.get('Subject')
    city_contains_query = request.GET.get('City')
    tuition_gender_query = request.GET.get('tuition_gender')
    number = tutors.count()

    if tutors:
        if tuition_level_contains_query != "" and tuition_level_contains_query is not None and tuition_level_contains_query != "All":
            tutors = tutors.filter(tuition_level = tuition_level_contains_query).order_by("-id")
            number = tutors.count()

        if subject_contains_query != "" and subject_contains_query is not None:
            tutors = tutors.filter(subject__icontains = subject_contains_query).order_by("-id")
            number = tutors.count()

        if city_contains_query != "" and city_contains_query is not None:
            tutors = tutors.filter(tutorUser__city__icontains = city_contains_query).order_by("-id")
            number = tutors.count()

        if tuition_gender_query != "" and tuition_gender_query is not None and tuition_gender_query != "Both":
            tutors = tutors.filter(tutorUser__gender__startswith = tuition_gender_query.lower())
            number = tutors.count()

    tuts = []
    if tutors:
        for t in tutors:
            tuts.append(t)

    paginator = Paginator(tuts,8)
    page = request.GET.get('page')
    try:
        items = paginator.page(page)
    except PageNotAnInteger:
        items = paginator.page(1)
    except EmptyPage:
        items = paginator.page(paginator.num_pages)

    index = items.number - 1
    max_index = len(paginator.page_range)
    start_index = index - 5 if index >= 5 else 0
    end_index = index + 5 if index <= max_index - 5 else max_index
    page_range = paginator.page_range[start_index:end_index]

    context = {
        # "tutors":items,
        "items":items,
        "number": number,
        "student": request.user.student,
        "page_range": page_range,
    }
    return render(request, 'students/all_tutors.html', context)

from tutors.models import AboutAndQualifications

@login_required(login_url="sign_in")
@allowed_users(allowed_roles=["students"])
def SpecificTutor(request, id):
    tutor = PostAnAd_tutor.objects.get(id = id)
    qual = AboutAndQualifications.objects.get(tutor__username = tutor.tutorUser.username)
    tutor.views += 1
    tutor.save()
    tutors = PostAnAd_tutor.objects.filter(tutorUser__username = tutor.tutorUser.username).order_by("-id")

    try:
        wishList = WishList.objects.get(student = request.user.student)
    except:
        wishList = None

    added = False
    if wishList is not None:
        if tutor.tutorUser in wishList.tutors.all():
            added = True

    context = {
        "tutor_id": tutor.tutorUser,
        "tutor": tutor,
        "qual": qual,
        "tutors": tutors.exclude(id = id),
        "student": request.user.student,
        "added":added,
    }
    return render (request, "students/specific_tutor.html", context)

from tutors.models import Tutor

@login_required(login_url="sign_in")
@allowed_users(allowed_roles=["students"])
def inviteFordemo(request, id):
    ad = PostAnAd_tutor.objects.get(id = id)

    tutor = Tutor.objects.get ( username = ad.tutorUser.username)

    user = Student.objects.get(username = request.user.username)

    std = Student.objects.get(username = request.user.username)
    try:
        invites_sent_by_std = Invitaions.objects.get(tutor_ad = ad)
    except:
        invites_sent_by_std = None

    if request.method == "POST":
        if invites_sent_by_std != None:
            if invites_sent_by_std.invitation_sent == True and invites_sent_by_std.inivitaion_by_student.username == request.user.username:
                messages.info(request, f'Invitation request already sent to {ad.tutorUser.first_name} {ad.tutorUser.last_name}')
                return redirect("all_tutors")
            else:
                Invitaions.objects.create(
                    inivitaion_by_student = std,
                    tutor_ad = ad,
                    invitation_sent = True,
                    accepted = False,
                    rejected = False
                )
                user.invitations_sent += 1
                user.save()
                tutor.invitations_recieved += 1
                tutor.save()

                template = render_to_string("home/inviteEmail.html", {
                    "firstname": ad.tutorUser.first_name,
                    "lastname": ad.tutorUser.last_name,
                    "ad": ad,
                    "invited_to": "Tutor",
                    "area":ad.address,
                    "city":ad.tutorUser.city
                    })
                registerEmail = EmailMessage(
                    'Invite For Demo',
                    template,
                    settings.EMAIL_HOST_USER,
                    [request.user.email]
                )
                registerEmail.fail_silently = False
                registerEmail.send()

                intemplate = render_to_string("home/invitationEmail.html", {
                "firstname": request.user.student.first_name,
                "lastname": request.user.student.last_name,
                "ad": ad,
                "invited_to": "Tutor",
                "area":ad.address,
                "city":ad.tutorUser.city
                    })

                email = EmailMessage(
                    'Invitation',
                    intemplate,
                    settings.EMAIL_HOST_USER,
                    [ad.tutorUser.email]
                )
                email.fail_silently = False
                email.send()

                messages.info(request, f'Invited {tutor.first_name} {tutor.last_name} For A Demo')
                return redirect("invited")

        else:
            Invitaions.objects.create(
                    inivitaion_by_student = std,
                    tutor_ad = ad,
                    invitation_sent = True,
                    accepted = False,
                    rejected = False
                )
            user.invitations_sent += 1
            user.save()
            tutor.invitations_recieved += 1
            tutor.save()

            template = render_to_string("home/inviteEmail.html", {
                    "firstname": ad.tutorUser.first_name,
                    "lastname": ad.tutorUser.last_name,
                    "ad": ad,
                    "invited_to": "Tutor",
                    "area":ad.address,
                    "city":ad.tutorUser.city
                    })
            registerEmail = EmailMessage(
                'Invite For Demo',
                template,
                settings.EMAIL_HOST_USER,
                [request.user.email]
            )
            registerEmail.fail_silently = False
            registerEmail.send()



            intemplate = render_to_string("home/invitationEmail.html", {
                    "firstname": request.user.student.first_name,
                    "lastname": request.user.student.last_name,
                    "ad": ad,
                    "invited_to": "Tutor",
                    "area":ad.address,
                    "city":ad.tutorUser.city
                    })
            email = EmailMessage(
                'Invitation',
                intemplate,
                settings.EMAIL_HOST_USER,
                [ad.tutorUser.email]
            )
            email.fail_silently = False
            email.send()

            messages.info(request, f'Invited {tutor.first_name} {tutor.last_name} For A Demo')
            return redirect("invited")
    context = {
        "ad":ad
    }
    return render(request, 'students/invite_for_demo.html', context)

@login_required(login_url="sign_in")
@allowed_users(allowed_roles=["students"])
def invited(request):
    student = Student.objects.get(username = request.user.username)
    invited = Invitaions.objects.filter(inivitaion_by_student= student).order_by("-id")
    context={
        "invited": invited,
    }
    return render(request, "students/invited.html", context)

@login_required(login_url="sign_in")
@allowed_users(allowed_roles=["students"])
def invitations(request):
    invites = TutorInvitaions.objects.filter(student_ad__studentUser = request.user.student).order_by("-id")
    context = {
        "invites":invites
    }

    return render(request, 'students/invitations.html', context)

@login_required(login_url="sign_in")
@allowed_users(allowed_roles=["students"])
def view_your_ad(request, id):
    student_ad = TutorInvitaions.objects.get(id = id)
    try:
        tutors = PostAnAd_tutor.objects.filter(subject = student_ad.student_ad.subject)[4]
    except:
        tutors = PostAnAd_tutor.objects.filter(subject = student_ad.student_ad.subject)

    context = {
        "invite":student_ad,
        "tutors": tutors.exclude(tutorUser__username = student_ad.inivitaion_by_tutor.username)
    }
    return render(request,'students/view_your_ad.html', context)

@login_required(login_url="sign_in")
@allowed_users(allowed_roles=["students"])
def acceptInvitation(request, id):
    invite = TutorInvitaions.objects.get(id = id)

    student = Student.objects.get(username = request.user.username)
    tutor = Tutor.objects.get(username = invite.inivitaion_by_tutor.username)
    if request.method == "POST":

        invite.accepted = True
        invite.rejected = False
        invite.save()
        student.invitations_recieved_accepted += 1
        student.save()
        tutor.invitations_sent_accepted += 1
        tutor.save()


        template = render_to_string("home/acceptEmail.html", {
                    "firstname": request.user.student.first_name,
                    "lastname": request.user.student.last_name,
                    "email": request.user.email,
                    "register_as": "Student",
                    "phone": request.user.student.phone
                    })
        registerEmail = EmailMessage(
            'Invitation Accepted',
            template,
            settings.EMAIL_HOST_USER,
            [invite.inivitaion_by_tutor.email]
        )
        registerEmail.fail_silently = False
        registerEmail.send()

        recieve_temp = render_to_string("home/accept_recieve_Email.html", {
                    "request_from" :tutor,
                    "request": "Tutor"
                    })
        Email = EmailMessage(
            'Invitation Accepted',
            recieve_temp,
            settings.EMAIL_HOST_USER,
            [request.user.email]
        )
        Email.fail_silently = False
        Email.send()

        messages.info(request, f'Accepted Invitation Request from {tutor.first_name} {tutor.last_name}')
        return redirect("invitations_student")
    context = {
        "invite":invite
    }

    return render(request, "students/accept_invitation.html", context)

@login_required(login_url="sign_in")
@allowed_users(allowed_roles=["students"])
def rejectInvite(request, id):
    invite = TutorInvitaions.objects.get(id = id)

    student = Student.objects.get(username = request.user.username)
    tutor = Tutor.objects.get(username = invite.inivitaion_by_tutor.username)
    if request.method == "POST":
        invite.delete()
        student.invitations_recieved_rejected += 1
        student.save()

        tutor.invitations_sent_rejected += 1
        tutor.save()

        template = render_to_string("home/rejectEmail.html", {
                    "firstname": request.user.student.first_name,
                    "lastname": request.user.student.last_name,
                    "student_email": request.user.email
                    })
        registerEmail = EmailMessage(
            'Invitation Rejected',
            template,
            settings.EMAIL_HOST_USER,
            [invite.inivitaion_by_tutor.email]
        )
        registerEmail.fail_silently = False
        registerEmail.send()

        messages.warning(request, f'Rejected Invite From {tutor.first_name} {tutor.last_name}')
        return redirect("invitations_student")
    context = {
    "invite": invite
    }
    return render(request,'students/reject_invitation.html', context)


@login_required(login_url="sign_in")
@allowed_users(allowed_roles=["students"])
def aboutStudent(request):
    aboutForm  = AboutStudentForm()


    if request.method == "POST":
        aboutForm = AboutStudentForm(request.POST)
        if aboutForm.is_valid():
            try:
                AboutStudent.objects.get(student__username = request.user.username).delete()
            except:
                pass
            about = aboutForm.cleaned_data["textArea"]
            std = Student.objects.get(username=request.user.username)
            std.profile_complete = True
            std.textArea = about
            std.save()
            return redirect("student_dashboard")
    context = {
        "form": aboutForm
    }

    return render(request, "students/student_about.html", context)


@login_required(login_url="sign_in")
@allowed_users(allowed_roles=["students"])
def del_account_student(request):
    student = User.objects.get(username = request.user.username)
    print(request.user.student.first_name)
    if request.method == "POST":
        student.is_active = False
        student.save()

        template = render_to_string("home/delEmail.html", {
                "register_as": "student",
                "email": request.user.email,
            })
        registerEmail = EmailMessage(
            'Account Deletion',
            template,
            settings.EMAIL_HOST_USER,
            [request.user.email]
        )
        registerEmail.fail_silently = False
        registerEmail.send()


        return redirect("student_dashboard")
    context = {}
    return render(request, "students/del_account.html", context)



class PostLikeToggle(RedirectView):
    def get_redirect_url(self, *args, **kwargs):
        id = self.kwargs.get("id")
        print(id)
        post = PostAnAd_tutor.objects.get(id=id)
        url_ = post.get_absolute_url()
        user = self.request.user
        student = user.student
        if student in post.likes.all():
            post.likes.remove(student)
        else:
            post.likes.add(student)
        return url_


from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import authentication, permissions


def add_like(post,std):
    post.likes.add(std)


def send_email(post,student):
    template = render_to_string("home/post_like_email.html", {
                "user":student,
                "post":post,
                "owner":post.tutorUser
            })
    postLikeEmail = EmailMessage(
        f'{student.first_name} {student.last_name} liked your AD',
        template,
        settings.EMAIL_HOST_USER,
        [post.tutorUser.email]
    )
    postLikeEmail.fail_silently = False
    postLikeEmail.send()

class PostLikeAPIToggle(APIView):

    authentication_classes = [authentication.SessionAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, id=None ,format=None):

        post = PostAnAd_tutor.objects.get(id=id)
        user = self.request.user
        student = user.student
        updated = False
        liked = False

        if student in post.likes.all():
            liked = False
            updated = True
            post.likes.remove(student)
        else:
            liked = True
            updated = True
            t1 = threading.Thread(target=add_like, args=[post,student])
            t2 = threading.Thread(target=send_email, args=[post,student])

            t1.start()
            t2.start()

        data = {
            "updated":updated,
            "liked":liked
        }
        return Response(data)

class WishlistApi(APIView):
    authentication_classes = [authentication.SessionAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, id=None ,format=None):
        tutor = Tutor.objects.get(id=id)
        student = request.user.student
        updated = False
        added = False

        wishlist,created = WishList.objects.get_or_create(student=student)
        wishlist_std,created = WishList_std.objects.get_or_create(tutor=tutor)

        if tutor in wishlist.tutors.all():
            updated = True
            added = False
            wishlist.tutors.remove(tutor)
            wishlist_std.students.remove(student)
        else:
            updated = True
            added = True
            wishlist.tutors.add(tutor)
            wishlist_std.students.add(student)

        data = {
            "updated":updated,
            "added":added
        }
        return Response(data)


def wishList(request):
    try:
        wishlist = WishList.objects.get(student=request.user.student)
    except:
        wishlist = None

    if wishlist is not None:
        tutors = wishlist.tutors.all()
    else:
        tutors = []

    context = {
        "tutors":tutors
    }
    return render(request,'students/wishlist.html',context)
