import os
from werkzeug.utils import secure_filename
from PIL import Image
import uuid

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
IMAGE_SIZES = {
    'thumbnail': (150, 150),
    'medium': (400, 400),
    'large': (800, 800)
}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_image(file, folder='uploads', sizes=None):
    """
    Save an image file with optional resizing
    
    Args:
        file: FileStorage object
        folder: Subfolder within static directory
        sizes: Dictionary of size names and dimensions
        
    Returns:
        Dictionary containing filenames for each size
    """
    if not file or not allowed_file(file.filename):
        return None
        
    # Generate unique filename
    filename = secure_filename(file.filename)
    base_filename = f"{str(uuid.uuid4())}-{filename}"
    
    # Ensure folder exists
    folder_path = os.path.join('static', folder)
    os.makedirs(folder_path, exist_ok=True)
    
    # Save original file
    file_path = os.path.join(folder_path, base_filename)
    file.save(file_path)
    
    result = {'original': os.path.join(folder, base_filename)}
    
    # Create resized versions if requested
    if sizes:
        img = Image.open(file_path)
        
        for size_name, dimensions in sizes.items():
            size_filename = f"{os.path.splitext(base_filename)[0]}-{size_name}{os.path.splitext(base_filename)[1]}"
            size_path = os.path.join(folder_path, size_filename)
            
            # Resize image maintaining aspect ratio
            resized_img = img.copy()
            resized_img.thumbnail(dimensions, Image.Resampling.LANCZOS)
            resized_img.save(size_path, quality=85, optimize=True)
            
            result[size_name] = os.path.join(folder, size_filename)
    
    return result

def delete_image(filename, folder='uploads', sizes=None):
    """
    Delete an image and its resized versions
    
    Args:
        filename: Base filename without folder
        folder: Subfolder within static directory
        sizes: List of size names to delete
    """
    # Delete original
    file_path = os.path.join('static', folder, filename)
    if os.path.exists(file_path):
        os.remove(file_path)
    
    # Delete resized versions
    if sizes:
        base_name = os.path.splitext(filename)[0]
        ext = os.path.splitext(filename)[1]
        
        for size in sizes:
            size_path = os.path.join('static', folder, f"{base_name}-{size}{ext}")
            if os.path.exists(size_path):
                os.remove(size_path)
