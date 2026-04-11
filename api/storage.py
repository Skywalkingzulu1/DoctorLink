"""
Filebase S3 Storage API for DoctorLink.
Supports avatars, medical reports, prescriptions, and chat media.
"""

import os
import uuid
from datetime import datetime, timedelta
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from fastapi import APIRouter, UploadFile, File, HTTPException, Query, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel

router = APIRouter()

# Filebase configuration
FILEBASE_ACCESS_KEY = os.getenv("FILEBASE_ACCESS_KEY")
FILEBASE_SECRET_KEY = os.getenv("FILEBASE_SECRET_KEY")
BUCKET_NAME = "skyhealth"
S3_ENDPOINT = "https://s3.filebase.com"

if not FILEBASE_ACCESS_KEY or not FILEBASE_SECRET_KEY:
    print("WARNING: Filebase credentials not configured. Storage API will not work.")

# S3 client
_config = Config(
    region_name="us-east-1",
    signature_version="s3v4",
)

_s3_client = None


def get_s3_client():
    global _s3_client
    if _s3_client is None:
        _s3_client = boto3.client(
            "s3",
            endpoint_url=S3_ENDPOINT,
            aws_access_key_id=FILEBASE_ACCESS_KEY,
            aws_secret_access_key=FILEBASE_SECRET_KEY,
            config=_config,
        )
    return _s3_client


class StorageResponse(BaseModel):
    success: bool
    key: Optional[str] = None
    url: Optional[str] = None
    message: Optional[str] = None


def ensure_bucket_exists():
    """Create bucket if it doesn't exist."""
    if not FILEBASE_ACCESS_KEY or not FILEBASE_SECRET_KEY:
        print("Filebase credentials not set, skipping bucket creation")
        return False

    s3 = get_s3_client()
    try:
        s3.head_bucket(Bucket=BUCKET_NAME)
        print(f"Bucket {BUCKET_NAME} already exists")
        return True
    except ClientError:
        try:
            s3.create_bucket(Bucket=BUCKET_NAME)
            print(f"Bucket {BUCKET_NAME} created")
            return True
        except ClientError as e:
            print(f"Error creating bucket: {e}")
            return False


def get_public_url(key: str) -> str:
    """Get public URL for a file."""
    return f"{S3_ENDPOINT}/{BUCKET_NAME}/{key}"


def object_exists(key: str) -> bool:
    """Check if an object exists in the bucket."""
    s3 = get_s3_client()
    try:
        s3.head_object(Bucket=BUCKET_NAME, Key=key)
        return True
    except ClientError:
        return False


def get_presigned_url(key: str, expires: int = 3600) -> str:
    """Get presigned URL for private files."""
    s3 = get_s3_client()
    try:
        url = s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": BUCKET_NAME, "Key": key},
            ExpiresIn=expires,
        )
        return url
    except ClientError as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate URL: {str(e)}")


def generate_presigned_upload_url(
    folder: str,
    filename: str,
    content_type: str = "application/octet-stream",
    expires: int = 3600,
) -> str:
    """Generate presigned URL for direct upload from client."""
    s3 = get_s3_client()
    key = f"{folder}/{filename}"

    try:
        url = s3.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": BUCKET_NAME,
                "Key": key,
                "ContentType": content_type,
            },
            ExpiresIn=expires,
        )
        return url
    except ClientError as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to generate upload URL: {str(e)}"
        )


async def upload_file_to_folder(
    file: UploadFile, folder: str, filename: Optional[str] = None
) -> str:
    """Upload a file to a folder in the bucket."""
    if not FILEBASE_ACCESS_KEY or not FILEBASE_SECRET_KEY:
        raise HTTPException(status_code=503, detail="Storage not configured")

    s3 = get_s3_client()

    # Generate unique filename if not provided
    if filename is None:
        ext = os.path.splitext(file.filename)[1] if file.filename else ""
        filename = f"{uuid.uuid4()}{ext}"

    key = f"{folder}/{filename}"

    # Read file content
    content = await file.read()

    try:
        s3.put_object(
            Bucket=BUCKET_NAME,
            Key=key,
            Body=content,
            ContentType=file.content_type or "application/octet-stream",
        )
        return key
    except ClientError as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


# ================= ROUTES =================


@router.get("/health")
async def storage_health():
    """Health check for storage."""
    if not FILEBASE_ACCESS_KEY or not FILEBASE_SECRET_KEY:
        return JSONResponse(
            status_code=503,
            content={"status": "error", "message": "Storage not configured"},
        )

    try:
        s3 = get_s3_client()
        s3.head_bucket(Bucket=BUCKET_NAME)
        return {"status": "ok", "bucket": BUCKET_NAME}
    except Exception as e:
        return JSONResponse(
            status_code=503, content={"status": "error", "message": str(e)}
        )


@router.post("/upload/avatar")
async def upload_avatar(user_id: str = Query(...), file: UploadFile = File(...)):
    """Upload doctor/patient avatar/profile photo."""
    key = await upload_file_to_folder(file, "avatars", f"{user_id}.jpg")
    url = get_public_url(key)

    return StorageResponse(
        success=True, key=key, url=url, message="Avatar uploaded successfully"
    )


@router.get("/avatar/{user_id}")
async def get_avatar(user_id: str):
    """Get avatar URL for a user."""
    try:
        key = f"avatars/{user_id}.jpg"

        exists = object_exists(key)
        if not exists:
            return StorageResponse(success=False, message="Avatar not found")

        url = get_public_url(key)
        return StorageResponse(success=True, key=key, url=url)
    except Exception as e:
        return StorageResponse(success=False, message=f"Error: {str(e)}")


@router.post("/upload/report")
async def upload_report(appointment_id: str = Query(...), file: UploadFile = File(...)):
    """Upload medical report (doctor only)."""
    filename = f"{appointment_id}_report.pdf"
    key = await upload_file_to_folder(file, "reports", filename)
    url = get_presigned_url(key)

    return StorageResponse(
        success=True, key=key, url=url, message="Report uploaded successfully"
    )


@router.get("/report/{appointment_id}")
async def get_report(appointment_id: str):
    """Get medical report URL (presigned for owner)."""
    key = f"reports/{appointment_id}_report.pdf"

    if not object_exists(key):
        return StorageResponse(success=False, message="Report not found")

    url = get_presigned_url(key)
    return StorageResponse(success=True, key=key, url=url)


@router.post("/upload/prescription")
async def upload_prescription(
    prescription_id: str = Query(...), file: UploadFile = File(...)
):
    """Upload prescription image."""
    key = await upload_file_to_folder(file, "prescriptions", f"{prescription_id}.jpg")
    url = get_presigned_url(key)

    return StorageResponse(
        success=True, key=key, url=url, message="Prescription uploaded successfully"
    )


@router.get("/prescription/{prescription_id}")
async def get_prescription(prescription_id: str):
    """Get prescription URL (presigned)."""
    key = f"prescriptions/{prescription_id}.jpg"

    if not object_exists(key):
        return StorageResponse(success=False, message="Prescription not found")

    url = get_presigned_url(key)
    return StorageResponse(success=True, key=key, url=url)


@router.get("/presigned-upload")
async def get_presigned_upload_url(
    folder: str = Query(..., description="avatars, reports, prescriptions, chat"),
    filename: str = Query(...),
    content_type: str = Query("application/octet-stream"),
):
    """Generate presigned URL for direct client upload."""
    # Validate folder
    allowed_folders = ["avatars", "reports", "prescriptions", "chat"]
    if folder not in allowed_folders:
        raise HTTPException(
            status_code=400, detail=f"Invalid folder. Allowed: {allowed_folders}"
        )

    url = generate_presigned_upload_url(folder, filename, content_type)

    return StorageResponse(
        success=True,
        key=f"{folder}/{filename}",
        url=url,
        message="Presigned upload URL generated",
    )


@router.delete("/file/{path:path}")
async def delete_file(path: str):
    """Delete a file."""
    s3 = get_s3_client()

    try:
        s3.delete_object(Bucket=BUCKET_NAME, Key=path)
        return StorageResponse(success=True, message="File deleted successfully")
    except ClientError as e:
        raise HTTPException(status_code=500, detail=f"Delete failed: {str(e)}")


@router.post("/upload/avatar")
async def upload_avatar(
    user_id: int = Query(..., description="User ID"), file: UploadFile = File(...)
):
    """Upload user avatar."""
    try:
        key = f"avatars/{user_id}.jpg"
        content = await file.read()

        s3 = get_s3_client()
        s3.put_object(
            Bucket=BUCKET_NAME,
            Key=key,
            Body=content,
            ContentType=file.content_type or "image/jpeg",
        )

        url = get_public_url(key)
        return StorageResponse(
            success=True, key=key, url=url, message="Avatar uploaded successfully"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")
