import base64
import io
import os
import platform
import mss
import mimetypes

from PIL import ImageGrab, Image
from mimetypes import guess_type
from collections import namedtuple


ImageCaptureResult = namedtuple('ImageCaptureResult', ['byte_data', 'img'])

def image_base64_encode(image_path):
    mime_type, _ = guess_type(image_path)
    mime_type = mime_type or 'application/octet-stream'
    with open(image_path, "rb") as image_file:
        base64_encoded_data = base64.b64encode(image_file.read()).decode('utf-8')
    return f"data:{mime_type};base64,{base64_encoded_data}"

def image_obj_base64_encode(file_obj):
    file_obj.seek(0)
    encoded = base64.b64encode(file_obj.read()).decode('utf-8')
    mime_type = file_obj.content_type
    if not mime_type or not mime_type.startswith("image/"):
        mime_type, _ = mimetypes.guess_type(file_obj.name)
        if not mime_type:
            mime_type = "image/png"  
    print(f"mime_type: {mime_type}")  
    data_url = f"data:{mime_type};base64,{encoded}"
    print(f"data_url head: {data_url[:50]}")  
    return data_url

def capture_image_from_currentBoundingRectangle(control_bounding_rect, padding=10, left_extra=0, right_extra=0, top_extra=0, bottom_extra=0):
    try:
        if platform.system().lower() == 'windows':
            left = control_bounding_rect.left
            top = control_bounding_rect.top
            right = control_bounding_rect.right
            bottom = control_bounding_rect.bottom
        elif platform.system().lower() == 'darwin':
            left = control_bounding_rect.x
            top = control_bounding_rect.y
            right = control_bounding_rect.x + control_bounding_rect.width
            bottom = control_bounding_rect.y + control_bounding_rect.height
            left, top, right, bottom = map(int, (left, top, right, bottom))
        
        left -= (padding + left_extra)
        right += (padding + right_extra)
        top -= (padding - top_extra)
        bottom += (padding - bottom_extra)
        
        with mss.mss() as sct:
            screenshot = sct.grab({'left': left, 'top': top, 'width': right - left, 'height': bottom - top})
            img = Image.frombytes('RGB', (screenshot.width, screenshot.height), screenshot.rgb)
        
        byte_io = io.BytesIO()
        img.save(byte_io, format='png')
        byte_data = byte_io.getvalue()
        
        return ImageCaptureResult(byte_data=byte_data, img=img)
    
    except Exception as e:
        print(f"Error capturing image: {e}")
        return ImageCaptureResult(byte_data=None, img=None)

def save_image(image_name, image_data=None, img=None, output_path="."):
    """
    :param image_data: The binary image data (optional).
    :param img: The PIL.Image object (optional).
    """
    if not os.path.exists(output_path):
        os.makedirs(output_path)

    file_name = os.path.join(output_path, f"{image_name}.png").replace(os.sep, '/')
    try:
        if img is not None:
            img.save(file_name)
        elif image_data is not None:
            image = Image.open(io.BytesIO(image_data))
            image.save(file_name)
        else:
            raise ValueError("Either image_data or img must be provided.")
        
        # LOGGER_INFO(f"Image saved to {file_name}")
    except Exception as e:
        print(f"Error saving image: {e}")
