from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import JobListing, ScreeningQuestion, CommonScreeningQuestion
from .serializers import JobListingSerializer, ScreeningQuestionSerializer, CommonScreeningQuestionSerializer, JobListingCreateSerializer, JobListingUpdateSerializer


class JobListingListView(generics.ListCreateAPIView):
    queryset = JobListing.objects.all()
    serializer_class = JobListingSerializer

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


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def activate_job(request, pk):
    job = get_object_or_404(JobListing, pk=pk)
    job.status = 'Active'
    job.save()
    serializer = JobListingSerializer(job)
    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def deactivate_job(request, pk):
    job = get_object_or_404(JobListing, pk=pk)
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
    original_job.id = None  # Reset the ID to create a new instance
    original_job.title = f"{original_job.title} (Copy)"
    original_job.status = 'Inactive'  # New copies start as inactive
    original_job.application_link = original_job.__class__._meta.get_field('application_link').default()
    original_job.created_by = request.user
    original_job.save()

    # Copy associated screening questions
    original_questions = ScreeningQuestion.objects.filter(job_listing_id=pk)
    for question in original_questions:
        question.id = None  # Reset the ID
        question.job_listing = original_job
        question.save()

    serializer = JobListingSerializer(original_job)
    return Response(serializer.data, status=status.HTTP_201_CREATED)


class ScreeningQuestionListView(generics.ListCreateAPIView):
    serializer_class = ScreeningQuestionSerializer

    def get_queryset(self):
        job_id = self.kwargs['job_id']
        return ScreeningQuestion.objects.filter(job_listing_id=job_id)

    def perform_create(self, serializer):
        job_id = self.kwargs['job_id']
        job = get_object_or_404(JobListing, pk=job_id)
        serializer.save(job_listing=job)


class ScreeningQuestionDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = ScreeningQuestion.objects.all()
    serializer_class = ScreeningQuestionSerializer


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_common_screening_questions(request):
    """
    Return a list of common screening questions that can be suggested to users
    """
    questions = CommonScreeningQuestion.objects.filter(is_active=True)
    serializer = CommonScreeningQuestionSerializer(questions, many=True)
    return Response(serializer.data)
