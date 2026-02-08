from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied
from .models import JobListing, ScreeningQuestion, CommonScreeningQuestion
from .serializers import JobListingSerializer, ScreeningQuestionSerializer, CommonScreeningQuestionSerializer, JobListingCreateSerializer, JobListingUpdateSerializer


from rest_framework.pagination import PageNumberPagination

class JobListingListPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'limit'
    max_page_size = 100

class JobListingListView(generics.ListCreateAPIView):
    queryset = JobListing.objects.all()
    serializer_class = JobListingSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = JobListingListPagination

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return JobListingCreateSerializer
        return self.serializer_class

    def get_queryset(self):
        queryset = JobListing.objects.all()
        status_param = self.request.query_params.get('status', None)
        if status_param:
            queryset = queryset.filter(status=status_param)
        return queryset

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class JobListingDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = JobListing.objects.all()
    serializer_class = JobListingSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # For update/delete, restrict to owned jobs; allow retrieve for all
        if self.request.method in ['PUT', 'PATCH', 'DELETE']:
            return JobListing.objects.filter(created_by=self.request.user)
        return JobListing.objects.all()


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def activate_job(request, pk):
    job = get_object_or_404(JobListing, pk=pk)

    # Check if the requesting user is the owner of the job
    if job.created_by != request.user:
        return Response(
            {'error': 'You do not have permission to activate this job.'},
            status=status.HTTP_403_FORBIDDEN
        )

    job.status = 'Active'
    job.save()
    serializer = JobListingSerializer(job)
    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def deactivate_job(request, pk):
    job = get_object_or_404(JobListing, pk=pk)

    # Check if the requesting user is the owner of the job
    if job.created_by != request.user:
        return Response(
            {'error': 'You do not have permission to deactivate this job.'},
            status=status.HTTP_403_FORBIDDEN
        )

    job.status = 'Inactive'
    job.save()
    serializer = JobListingSerializer(job)
    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def duplicate_job(request, pk):
    original_job = get_object_or_404(JobListing, pk=pk)

    # Check if the requesting user is the owner of the job
    if original_job.created_by != request.user:
        return Response(
            {'error': 'You do not have permission to duplicate this job.'},
            status=status.HTTP_403_FORBIDDEN
        )

    # Create a new job with the same details but different ID
    field_def = original_job.__class__._meta.get_field('application_link')
    new_application_link = field_def.default() if callable(field_def.default) else field_def.default

    new_job = JobListing(
        title=f"{original_job.title} (Copy)",
        description=original_job.description,
        required_skills=original_job.required_skills,
        required_experience=original_job.required_experience,
        job_level=original_job.job_level,
        start_date=original_job.start_date,
        expiration_date=original_job.expiration_date,
        modification_date=original_job.modification_date,
        status='Inactive',  # New copies start as inactive
        application_link=new_application_link,
        created_by=request.user
    )
    new_job.save()

    # Copy associated screening questions
    original_questions = ScreeningQuestion.objects.filter(job_listing_id=pk)
    for question in original_questions:
        new_question = ScreeningQuestion(
            job_listing=new_job,
            question_text=question.question_text,
            question_type=question.question_type,
            required=question.required,
            order=question.order,
            choices=question.choices
        )
        new_question.save()

    serializer = JobListingSerializer(new_job)
    return Response(serializer.data, status=status.HTTP_201_CREATED)


class ScreeningQuestionListView(generics.ListCreateAPIView):
    serializer_class = ScreeningQuestionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        job_id = self.kwargs['job_id']
        # Only return questions for job listings owned by the current user
        return ScreeningQuestion.objects.filter(
            job_listing_id=job_id,
            job_listing__created_by=self.request.user
        )

    def perform_create(self, serializer):
        job_id = self.kwargs['job_id']
        job = get_object_or_404(JobListing, pk=job_id)

        # Verify the user owns the job listing
        if job.created_by != self.request.user:
            raise PermissionDenied("You do not have permission to add questions to this job.")

        serializer.save(job_listing=job)


class ScreeningQuestionDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ScreeningQuestionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Only allow access to questions belonging to job listings owned by the current user
        return ScreeningQuestion.objects.filter(job_listing__created_by=self.request.user)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_common_screening_questions(request):
    """
    Return a list of common screening questions that can be suggested to users
    """
    questions = CommonScreeningQuestion.objects.filter(is_active=True)
    serializer = CommonScreeningQuestionSerializer(questions, many=True)
    return Response(serializer.data)