# Project Feature Implementation - Summary

## Overview
The project feature groups all generated content (Reels and Captions) from a single user operation into a unified project entity. This allows better organization and lifecycle management of generated content.

## Database Schema Changes

### Table: projects
**Location:** supabase/migrations/20260906_create_projects_table.sql

**Columns:**
- `id` (UUID, primary key)
- `user_id` (UUID, foreign key to auth.users)
- `name` (text) - Project name
- `description` (text, optional) - Project description
- `project_type` (enum: 'reel' | 'caption') - Type of content generated
- `source_type` (enum: 'upload' | 'youtube' | 'url') - Origin of source video
- `source_url` (text, optional) - Original source URL (for YouTube/URL sources)
- `source_s3_key` (text) - S3 key where source video is stored
- `source_duration` (integer, optional) - Duration in seconds
- `source_size` (bigint) - Size in bytes
- `thumbnail_url` (text, optional) - Project thumbnail
- `output_count` (integer) - Number of generated reels/captions
- `status` (enum: 'processing' | 'completed' | 'failed' | 'cancelled')
- `created_at` (timestamptz)
- `updated_at` (timestamptz)
- `completed_at` (timestamptz, optional) - Timestamp when project reaches terminal state

**Indexes:**
- idx_projects_user_created (user_id, created_at desc)
- idx_projects_status (status)
- idx_projects_type (project_type)
- idx_projects_name_trgm (full-text search)
- idx_projects_description_trgm (full-text search)
- idx_projects_completed_at (completed_at desc)
- idx_projects_user_status_date (user_id, status, created_at desc)

### Tables: reels and captions
**Location:** supabase/migrations/20260906_add_projects_to_reels_and_captions.sql

**New columns:**
- `reels.project_id` (UUID, foreign key to projects)
- `captions.project_id` (UUID, foreign key to projects)
- `reels.truthfulness_score` (integer, 0-100) - OpenAI truthfulness analysis

## Backend Implementation

### New Functions in supabase_request.py

#### update_project_status()
```python
async def update_project_status(project_id: str, status: str) -> Optional[Dict[str, Any]]
```
Updates project status to completed/failed/cancelled and sets completed_at timestamp.

#### get_reels_by_project()
```python
async def get_reels_by_project(project_id: str) -> List[Dict[str, Any]]
```
Retrieves all reels associated with a project.

#### get_captions_by_project()
```python
async def get_captions_by_project(project_id: str) -> List[Dict[str, Any]]
```
Retrieves all captions associated with a project.

### Modified Functions in app.py

#### Reel Job Processing
- `run_job()`: Updates project status to "completed" when reel generation succeeds
- `_finalize_failed_reel_job()`: Updates project status to "failed" when reel generation fails

#### Caption Job Processing
- `run_caption_job()`: Updates project status to "completed" when caption generation succeeds
- Exception handler in `run_caption_job()`: Updates project status to "failed" when caption generation fails

#### Project Management
- `delete_project_endpoint()`:
  - Deletes source S3 file
  - Deletes all reel files (videos + thumbnails)
  - Deletes all caption files (videos + thumbnails)
  - Calculates total freed storage
  - Updates user storage quota (frees up space)
  - Deletes all database records

## API Endpoints

### GET /api/projects
List all projects for a user with pagination and filtering.

**Query Parameters:**
- `page` (int, default=1)
- `page_size` (int, default=20, max=100)
- `project_type` (optional: 'reel' | 'caption')
- `status` (optional: 'processing' | 'completed' | 'failed' | 'cancelled')
- `q` (optional, search query for name/description)

**Response:**
```json
{
  "items": [...],
  "total": 42,
  "page": 1,
  "page_size": 20
}
```

### GET /api/projects/{project_id}
Get a single project by ID.

**Response:**
```json
{
  "id": "uuid",
  "user_id": "uuid",
  "name": "Project Name",
  "description": "Optional description",
  "project_type": "reel",
  "source_type": "upload",
  "source_url": null,
  "source_s3_key": "projects/job_id/source/video.mp4",
  "source_duration": 120,
  "source_size": 52428800,
  "thumbnail_url": "https://...",
  "output_count": 5,
  "status": "completed",
  "created_at": "2026-09-06T12:34:56Z",
  "updated_at": "2026-09-06T12:45:00Z",
  "completed_at": "2026-09-06T12:45:00Z"
}
```

### PUT /api/projects/{project_id}
Update project metadata (name and description only).

**Request Body:**
```json
{
  "name": "New Project Name",
  "description": "New description"
}
```

### DELETE /api/projects/{project_id}
Delete a project and all its associated content (reels, captions, S3 files).

**Behavior:**
1. Fetches all reels and captions associated with the project
2. Deletes all S3 files:
   - Source video (source_s3_key)
   - Reel media files (reel_s3_key)
   - Reel thumbnails (reel_thumbnail_url)
   - Caption media files (caption_s3_key)
   - Caption thumbnails (caption_thumbnail_url)
3. Calculates total freed storage in bytes
4. Deletes all database records (reels, captions, project)
5. Updates user storage quota to free up the space

### GET /api/projects/{project_id}/source-url
Get a pre-signed URL to download the project source video.

**Response:**
```json
{
  "source_url": "https://s3.amazonaws.com/..."
}
```

### GET /api/projects/{project_id}/reels
Get all reels generated from this project.

**Response:**
```json
{
  "project_id": "uuid",
  "reels": [...],
  "count": 5
}
```

### GET /api/projects/{project_id}/captions
Get all captions generated from this project.

**Response:**
```json
{
  "project_id": "uuid",
  "captions": [...],
  "count": 1
}
```

## Project Lifecycle

### Creation
1. User uploads video or provides YouTube/URL
2. Reel or Caption job starts with status="processing"
3. Project is created with:
   - Source video uploaded to S3: `projects/{job_id}/source/{filename}`
   - Status set to "processing"
   - Storage immediately deducted from user quota

### Processing
- Project status remains "processing" during content generation
- Output count is incremented each time a reel or caption is generated

### Completion
1. Job completes successfully
2. Project status updated to "completed"
3. Completed_at timestamp is set
4. All reels/captions associated with project are marked with project_id

### Failure
1. Job fails with error
2. Project status updated to "failed"
3. Completed_at timestamp is set
4. User can retry or delete the project to free up storage

### Deletion
1. User requests project deletion
2. All associated files deleted from S3
3. All database records deleted
4. Storage quota is freed

## Storage Management

### On Project Creation
- Source video size is immediately deducted from user's storage quota
- Formula: `new_used_storage = current_used_storage + source_size`

### On Reel/Caption Generation
- Generated file sizes are deducted from user's storage quota
- Formula: `new_used_storage = current_used_storage + generated_file_size`

### On Project Deletion
- All file sizes are added back to user's storage quota
- Formula: `new_used_storage = current_used_storage - total_project_files_size`

## Implementation Notes

1. **S3 Key Structure:** All project files are organized under `projects/{job_id}/` prefix:
   - Source: `projects/{job_id}/source/{filename}`
   - Reels: `reels/{user_id}/{job_id}/clip_{index}.mp4`
   - Thumbnails: `reels/{user_id}/{job_id}/thumbnail_{index}.jpg`
   - Captions: `captions/{user_id}/{job_id}/caption.mp4`

2. **Project-Job Relationship:** Each job creates exactly one project. The project_id is stored in the job's project_id field and passed through the entire processing pipeline.

3. **Status Synchronization:** Project status is automatically updated based on job completion/failure. This ensures frontend can always show accurate project status without additional queries.

4. **Orphaned Files Cleanup:** The periodic output sweep (existing mechanism) cleans up local files. S3 files are cleaned up during project deletion.

5. **Truthfulness Score:** Reels can optionally have a truthfulness_score (0-100) computed during video analysis.

## Testing Considerations

1. Verify project creation with different source types (upload, youtube, url)
2. Verify project status transitions during job execution
3. Verify project deletion properly frees all S3 files and storage quota
4. Verify endpoints return proper user ownership validation
5. Verify storage calculations are accurate during creation and deletion
6. Verify CAPTION_COLUMNS includes project_id for proper queries

