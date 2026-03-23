# Quickstart: Bulk Resumes Upload

**Feature**: 011-bulk-resume-upload  
**Date**: 2026-03-23  
**Audience**: Developers implementing the feature

---

## Overview

This feature allows Talent Acquisition Specialists to upload multiple resumes in bulk (max 100 files/batch, 3 batches/job listing) with drag-and-drop interface, duplicate detection, and automatic Applicant creation.

---

## Prerequisites

- Python 3.11
- Django 5.2.9 + Django REST Framework
- Celery 5.4.0 + Redis 7.1.0
- Existing services: `duplication_service.py`, `resume_parsing_service.py`

---

## Implementation Checklist

### Phase 1: Database Changes

- [ ] Create migration for JobListing model (upload_type, batch_count, total_resumes)
- [ ] Create migration for UploadBatch model
- [ ] Create migration for Applicant.upload_batch field
- [ ] Run migrations: `python manage.py migrate`

### Phase 2: Backend Implementation

**Serializers** (`apps/applications/serializers.py`):
- [ ] `BulkUploadInitSerializer` - Job listing ID validation
- [ ] `BulkUploadFileSerializer` - File upload handling
- [ ] `BulkUploadValidateSerializer` - Batch validation
- [ ] `BulkUploadCommitSerializer` - Batch commit
- [ ] `BulkUploadDecisionSerializer` - Duplicate decisions
- [ ] `BulkUploadSummarySerializer` - Response formatting

**API Views** (`apps/applications/api.py`):
- [ ] `BulkUploadInitView` - POST /init/
- [ ] `BulkUploadView` - POST /upload/
- [ ] `BulkUploadValidateView` - POST /validate/
- [ ] `BulkUploadCommitView` - POST /commit/
- [ ] `BulkUploadCancelView` - DELETE /cancel/<batch_id>/
- [ ] `BulkUploadStatusView` - GET /status/<batch_id>/
- [ ] `BulkUploadSummaryView` - GET /summary/<batch_id>/

**Celery Tasks** (`apps/applications/tasks.py`):
- [ ] `process_resume_async` - Parse and create Applicant
- [ ] `send_bulk_upload_notification` - Email notification

**URLs** (`apps/applications/urls.py`):
```python
urlpatterns = [
    path('bulk-upload/init/', BulkUploadInitView.as_view(), name='bulk-upload-init'),
    path('bulk-upload/upload/', BulkUploadView.as_view(), name='bulk-upload-upload'),
    path('bulk-upload/validate/', BulkUploadValidateView.as_view(), name='bulk-upload-validate'),
    path('bulk-upload/commit/', BulkUploadCommitView.as_view(), name='bulk-upload-commit'),
    path('bulk-upload/cancel/<uuid:batch_id>/', BulkUploadCancelView.as_view(), name='bulk-upload-cancel'),
    path('bulk-upload/status/<uuid:batch_id>/', BulkUploadStatusView.as_view(), name='bulk-upload-status'),
    path('bulk-upload/summary/<uuid:batch_id>/', BulkUploadSummaryView.as_view(), name='bulk-upload-summary'),
]
```

### Phase 3: Frontend Implementation

**Templates** (`apps/applications/templates/applications/`):
- [ ] `bulk_upload.html` - Main upload page with drag-and-drop
- [ ] `bulk_upload_progress.html` - Progress tracking modal
- [ ] `bulk_upload_summary.html` - Summary page after commit

**Static Files** (`apps/applications/static/`):
- [ ] `js/bulk_upload.js` - Drag-and-drop, file upload, WebSocket handling
- [ ] `css/bulk_upload.css` - Upload interface styling

**Jobs App Integration**:
- [ ] Update `create_job.html` template with upload_type selector
- [ ] Update job listing card template with conditional actions

### Phase 4: Testing

**Unit Tests** (`apps/applications/tests/Unit/`):
- [ ] `test_serializers.py` - Serializer validation
- [ ] `test_views.py` - API endpoint logic
- [ ] `test_models.py` - Model methods and constraints

**Integration Tests** (`apps/applications/tests/Integration/`):
- [ ] `test_duplication_service.py` - Service integration
- [ ] `test_parsing_service.py` - Resume parsing
- [ ] `test_storage.py` - File storage operations

**E2E Tests** (`apps/applications/tests/E2E/`):
- [ ] `test_bulk_upload_workflow.py` - Full workflow with Selenium

---

## File Upload Flow

```
1. User selects job listing → Click "Start Upload"
   ↓
2. Frontend calls POST /init/ → Gets batch_id
   ↓
3. User drags files → Frontend uploads each via POST /upload/
   ↓
4. After all files uploaded → POST /validate/
   ↓
5. Duplicates detected → Show review modal
   ↓
6. User makes decisions → POST /decisions/
   ↓
7. User confirms → POST /commit/
   ↓
8. Celery processes files → Creates Applicants
   ↓
9. Show summary page with results
```

---

## Key Code Examples

### Initializing Upload

```python
# apps/applications/api.py
class BulkUploadInitView(APIView):
    permission_classes = [IsAuthenticated, IsTAS]
    
    def post(self, request):
        serializer = BulkUploadInitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        job_listing = get_object_or_404(JobListing, id=serializer.validated_data['job_listing_id'])
        
        # Check if bulk upload allowed
        can_upload, message = job_listing.can_upload_batch(0)
        if not can_upload:
            return Response({'error': message}, status=400)
        
        # Create UploadBatch
        batch = UploadBatch.objects.create(
            job_listing=job_listing,
            batch_number=job_listing.batch_count + 1,
            uploaded_by=request.user,
            status='pending'
        )
        
        return Response({
            'batch_id': str(batch.id),
            'batch_number': batch.batch_number,
            'max_files': 100,
            'remaining_capacity': 100,
            'status': batch.status
        }, status=201)
```

### File Upload with Validation

```python
class BulkUploadView(APIView):
    permission_classes = [IsAuthenticated, IsTAS]
    
    def post(self, request):
        batch_id = request.data.get('batch_id')
        batch = get_object_or_404(UploadBatch, id=batch_id)
        
        # Check batch capacity
        if batch.file_count >= 100:
            return Response({'error': 'Batch full'}, status=400)
        
        file = request.FILES.get('file')
        file_content = file.read()
        
        # Validate file using existing service
        validation_result = DuplicationService.validate_resume_file(
            file_content, 
            file.name
        )
        
        if not validation_result['valid']:
            return Response({
                'error': validation_result['errors'][0]['code'],
                'message': validation_result['errors'][0]['message']
            }, status=400)
        
        # Store in temp location
        temp_path = f'applications/temp/{batch.id}/{file.name}'
        default_storage.save(temp_path, ContentFile(file_content))
        
        # Add to batch
        file_metadata = {
            'file_id': str(uuid.uuid4()),
            'filename': file.name,
            'file_hash': validation_result['file_hash'],
            'size': len(file_content),
            'temp_path': temp_path,
            'status': 'uploaded'
        }
        batch.add_file(file_metadata)
        
        return Response(file_metadata)
```

### Duplicate Detection

```python
class BulkUploadValidateView(APIView):
    permission_classes = [IsAuthenticated, IsTAS]
    
    def post(self, request):
        batch_id = request.data.get('batch_id')
        batch = get_object_or_404(UploadBatch, id=batch_id)
        
        duplicates = []
        valid_files = []
        
        for file_meta in batch.temp_files:
            # Check file hash duplicate
            if DuplicationService.check_resume_duplicate(
                batch.job_listing, 
                file_meta['file_hash']
            ):
                duplicates.append({
                    'file_id': file_meta['file_id'],
                    'filename': file_meta['filename'],
                    'duplicate_type': 'file_hash'
                })
                continue
            
            # Extract contact info for further checks
            text = ResumeParserService.extract_text_from_docx(
                default_storage.open(file_meta['temp_path']).read()
            )
            contact_info = extract_contact_info(text)
            
            # Check email duplicate
            if contact_info.get('email') and DuplicationService.check_email_duplicate(
                batch.job_listing, 
                contact_info['email']
            ):
                duplicates.append({
                    'file_id': file_meta['file_id'],
                    'filename': file_meta['filename'],
                    'duplicate_type': 'email',
                    'email': contact_info['email']
                })
                continue
            
            valid_files.append(file_meta)
        
        batch.duplicate_summary = {'duplicates': duplicates, 'valid_files': valid_files}
        batch.status = 'review'
        batch.save()
        
        return Response({
            'batch_id': str(batch.id),
            'total_files': len(batch.temp_files),
            'valid_files': len(valid_files),
            'duplicates': duplicates,
            'status': batch.status
        })
```

### Committing Batch

```python
class BulkUploadCommitView(APIView):
    permission_classes = [IsAuthenticated, IsTAS]
    
    def post(self, request):
        batch_id = request.data.get('batch_id')
        batch = get_object_or_404(UploadBatch, id=batch_id)
        
        # Validate ready to commit
        can_commit, message = batch.can_commit()
        if not can_commit:
            return Response({'error': message}, status=400)
        
        # Process files asynchronously
        for file_meta in batch.temp_files:
            if file_meta.get('action') == 'skip':
                continue
            
            # Move file to permanent storage
            permanent_path = f'applications/resumes/{batch.job_listing.id}/{file_meta["filename"]}'
            default_storage.save(permanent_path, default_storage.open(file_meta['temp_path']))
            default_storage.delete(file_meta['temp_path'])
            
            # Create Applicant
            applicant = Applicant.objects.create(
                job_listing=batch.job_listing,
                upload_batch=batch,
                first_name=file_meta.get('first_name', ''),
                last_name=file_meta.get('last_name', ''),
                email=file_meta.get('email', ''),
                phone=file_meta.get('phone', ''),
                resume_file=permanent_path,
                resume_file_hash=file_meta['file_hash'],
                resume_parsed_text=file_meta['redacted_text']
            )
        
        # Update JobListing counters
        batch.job_listing.batch_count += 1
        batch.job_listing.total_resumes += len([f for f in batch.temp_files if f.get('action') != 'skip'])
        batch.job_listing.save()
        
        batch.status = 'committed'
        batch.save()
        
        return Response({
            'batch_id': str(batch.id),
            'status': 'committed',
            'applicants_created': batch.file_count
        })
```

---

## WebSocket Consumer

```python
# apps/applications/consumers.py
class BulkUploadConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.batch_id = self.scope['url_route']['kwargs']['batch_id']
        self.room_group_name = f'bulk_upload_{self.batch_id}'
        
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        await self.accept()
    
    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
    
    async def upload_progress(self, event):
        await self.send(text_data=json.dumps({
            'type': 'file_progress',
            'file_id': event['file_id'],
            'status': event['status'],
            'progress_percent': event.get('progress_percent', 100)
        }))
    
    async def batch_progress(self, event):
        await self.send(text_data=json.dumps({
            'type': 'batch_progress',
            'files_uploaded': event['files_uploaded'],
            'files_total': event['files_total'],
            'status': event['status']
        }))
```

---

## Testing Commands

```bash
# Run unit tests
python manage.py test apps.applications.tests.Unit

# Run integration tests
python manage.py test apps.applications.tests.Integration

# Run E2E tests (requires Selenium)
python manage.py test apps.applications.tests.E2E

# Check test coverage
coverage run --source='apps.applications' manage.py test apps.applications.tests
coverage report --minimum=90
```

---

## Common Issues

### Issue: File upload timeout for large batches

**Solution**: Increase Django request timeout and use chunked upload
```python
# settings.py
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10MB
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10MB
```

### Issue: Duplicate detection slow

**Solution**: Ensure database indexes on resume_file_hash, email, phone
```python
# Already defined in Applicant model Meta.index
indexes = [
    models.Index(fields=['job_listing', 'resume_file_hash']),
    models.Index(fields=['job_listing', 'email']),
    models.Index(fields=['job_listing', 'phone']),
]
```

### Issue: WebSocket connection fails

**Solution**: Check Django Channels configuration and Redis connection
```python
# settings.py
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            'hosts': [('127.0.0.1', 6379)],
        },
    },
}
```

---

## Next Steps

After implementation:
1. Run all tests and verify 90% coverage
2. Test with 100-file batch to verify performance (SC-001: <2 minutes)
3. Verify duplicate detection accuracy (SC-003: 98% precision)
4. Test WebSocket fallback to polling
5. Verify constitution compliance (color grading, Dark Mode)
