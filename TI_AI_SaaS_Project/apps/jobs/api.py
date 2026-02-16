from django.shortcuts import get_object_or_404
from django.utils import timezone
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
        """
        Select the serializer class for the current request method.
        
        Returns:
            The serializer class to use: `JobListingCreateSerializer` for POST requests, otherwise the view's configured `serializer_class`.
        """
        if self.request.method == 'POST':
            return JobListingCreateSerializer
        return self.serializer_class

    def get_queryset(self):
        """
        Return the queryset of JobListing objects owned by the requesting user, optionally filtered by query parameters.
        
        Filters supported via query parameters:
        - status: exact match on the job's status.
        - date_range: restricts by creation date; accepted values are "today", "week", and "month".
        - job_level: exact match on the job_level field.
        - search: case-insensitive substring search applied to title and description.
        
        Returns:
            QuerySet: JobListing queryset filtered by ownership and any provided query parameters.
        """
        queryset = JobListing.objects.filter(created_by=self.request.user)
        
        # Apply status filter
        status_param = self.request.query_params.get('status', None)
        if status_param:
            queryset = queryset.filter(status=status_param)
        
        # Apply date range filter
        date_range_param = self.request.query_params.get('date_range', None)
        if date_range_param:
            now = timezone.now()
            if date_range_param == 'today':
                queryset = queryset.filter(created_at__date=now.date())
            elif date_range_param == 'week':
                from datetime import timedelta
                start_of_week = now - timedelta(days=now.weekday())
                queryset = queryset.filter(created_at__gte=start_of_week)
            elif date_range_param == 'month':
                queryset = queryset.filter(created_at__year=now.year, created_at__month=now.month)
        
        # Apply job level filter
        job_level_param = self.request.query_params.get('job_level', None)
        if job_level_param:
            queryset = queryset.filter(job_level=job_level_param)
        
        # Apply search filter
        search_param = self.request.query_params.get('search', None)
        if search_param:
            from django.db.models import Q
            queryset = queryset.filter(
                Q(title__icontains=search_param) | 
                Q(description__icontains=search_param)
            )
        
        return queryset

    def perform_create(self, serializer):
        """
        Persist a new instance from the provided serializer while assigning the current request user as its `created_by`.
        
        Parameters:
            serializer: A serializer instance containing validated data for the object to be created.
        """
        serializer.save(created_by=self.request.user)


class JobListingDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = JobListing.objects.all()
    serializer_class = JobListingSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # For update/delete, restrict to owned jobs; allow retrieve for all
        """
        Return the queryset for this detail view, restricting write operations to the requesting user's job listings.
        
        When the request method is PUT, PATCH, or DELETE, returns JobListing objects created by the requesting user; for other methods (e.g., GET) returns all JobListing objects.
        
        Returns:
            django.db.models.QuerySet: A queryset of JobListing instances filtered as described above.
        """
        if self.request.method in ['PUT', 'PATCH', 'DELETE']:
            return JobListing.objects.filter(created_by=self.request.user)
        return JobListing.objects.all()


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def activate_job(request, pk):
    """
    Activate a job listing owned by the requesting user.
    
    Attempts to set the JobListing identified by `pk` to status 'Active' if the requesting user is the listing's owner; otherwise returns a 403 response.
    
    Parameters:
    	request (HttpRequest): The incoming HTTP request; used to identify the authenticated user.
    	pk (int | str): Primary key of the JobListing to activate.
    
    Returns:
    	Response: Serialized job listing data on success; a 403 Forbidden response with an error message if the requester does not own the job.
    """
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
    """
    Deactivate a JobListing identified by primary key if the requesting user is the job's owner.
    
    Parameters:
        pk (int): Primary key of the JobListing to deactivate.
    
    Returns:
        Response: Serialized JobListing data after setting its status to 'Inactive'. If the requesting user does not own the job, returns a 403 Response with an error message.
    """
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
    """
    Create a duplicate of an existing job listing owned by the requesting user, including its screening questions.
    
    Parameters:
        request (rest_framework.request.Request): The incoming HTTP request; the request user becomes the owner of the duplicated job.
        pk (int): Primary key of the job listing to duplicate.
    
    Returns:
        rest_framework.response.Response: On success, a response with the serialized duplicated JobListing and HTTP 201 Created. If the requester is not the job owner, returns a 403 Forbidden response with an error message.
    """
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
        modification_date=timezone.now(),
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
        """
        Retrieve screening questions for the job specified by the URL that are owned by the requesting user.
        
        Returns:
            QuerySet[ScreeningQuestion]: ScreeningQuestion objects filtered by `job_id` from URL kwargs and by `created_by` matching the requesting user.
        """
        job_id = self.kwargs['job_id']
        # Only return questions for job listings owned by the current user
        return ScreeningQuestion.objects.filter(
            job_listing_id=job_id,
            job_listing__created_by=self.request.user
        )

    def perform_create(self, serializer):
        """
        Ensure a new ScreeningQuestion is saved for the specified job if the requesting user owns that job.
        
        Parameters:
            serializer: The serializer instance containing validated ScreeningQuestion data to persist.
        
        Raises:
            PermissionDenied: If the authenticated user is not the creator/owner of the target JobListing.
        """
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
        """
        Return screening questions that belong to job listings owned by the requesting user.
        
        Returns:
            QuerySet[ScreeningQuestion]: ScreeningQuestion objects whose related job_listing was created by the current user.
        """
        return ScreeningQuestion.objects.filter(job_listing__created_by=self.request.user)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_common_screening_questions(request):
    """
    Retrieve active common screening questions available for suggestion.
    
    Returns:
        A list of serialized common screening question objects containing only questions where `is_active` is True.
    """
    questions = CommonScreeningQuestion.objects.filter(is_active=True)
    serializer = CommonScreeningQuestionSerializer(questions, many=True)
    return Response(serializer.data)