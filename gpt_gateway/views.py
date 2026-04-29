import os
import json
from datetime import datetime
from django.http import JsonResponse

from django.shortcuts import render
from django.http import JsonResponse
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from rest_framework.response import Response
from rest_framework.decorators import api_view
from rest_framework import status
from gpt_gateway.models.openai_model import OpenAIModel
from gpt_gateway.utils.session_tracker import SessionTracker, record_request

def health_check_url(request):
    # Record session for health check
    record_request(request, response_status=200)
    return HttpResponse("The URL is working!")

openai_model = OpenAIModel()

@csrf_exempt
def chat(request):
    with SessionTracker(request) as tracker:
        try:
            message = request.GET.get('message', None)
            response = openai_model.get_response(message)
            print(f"response: {response}")
            tracker.set_response_status(200)
            response = HttpResponse(response, content_type='text/plain; charset=utf-8')
        except ValueError as e:
            tracker.set_response_status(400)
            tracker.set_error_message(str(e))
            return HttpResponse(str(e), status=400)
        return response

@csrf_exempt
def chat_sr(request):
    with SessionTracker(request) as tracker:
        if request.method == "POST":
            markdown_file = request.FILES.get('markdown_file')
            if markdown_file:
                try:
                    markdown_content = markdown_file.read().decode('utf-8')
                    response = openai_model.get_response_for_sr(markdown_content)
                    print(f"response: {response}")
                    tracker.set_response_status(200)
                    return HttpResponse(response, content_type='text/plain; charset=utf-8')
                except Exception as e:
                    tracker.set_response_status(400)
                    tracker.set_error_message(str(e))
                    return HttpResponse(f"Error processing file: {str(e)}", status=400)
            
            markdown_content = request.POST.get('markdown_content')
            if markdown_content:
                try:
                    response = openai_model.get_response_for_sr(markdown_content)
                    print(f"response: {response}")
                    tracker.set_response_status(200)
                    return HttpResponse(response, content_type='text/plain; charset=utf-8')
                except Exception as e:
                    tracker.set_response_status(400)
                    tracker.set_error_message(str(e))
                    return HttpResponse(f"Error processing content: {str(e)}", status=400)
            
            tracker.set_response_status(400)
            return JsonResponse({"error": "No markdown file or content provided"}, status=400)
        
        elif request.method == "GET":
            tracker.set_response_status(200)
            return JsonResponse({"message": "This API supports POST requests with markdown file or content for screen reader analysis."})
        
        else:
            tracker.set_response_status(405)
            return JsonResponse({"error": "Invalid request method"}, status=405)

@csrf_exempt
def chat_image(request):
    from gpt_gateway.utils.session_tracker import SessionTracker
    
    with SessionTracker(request) as tracker:
        if request.method == "POST" and request.FILES.get("file"):
            image_file = request.FILES["file"]
            
            if not image_file:
                tracker.set_response_status(400)
                return JsonResponse({"error": "No image file provided"}, status=400)

            # Ensure the images directory exists
            images_dir = "src/images"
            os.makedirs(images_dir, exist_ok=True)
            
            temp_path = os.path.join(images_dir, image_file.name)
            with open(temp_path, "wb") as f:
                for chunk in image_file.chunks():
                    f.write(chunk)
            
            # response = openai_chat_image.get_response(temp_path)
            response = "ImageAnalyzer temporarily disabled"
            
            tracker.set_response_status(200)
            return JsonResponse({"result": response})

        elif request.method == "GET":
            tracker.set_response_status(200)
            return JsonResponse({"message": "This API only supports POST requests with an image file."})

        else:
            tracker.set_response_status(405)
            return JsonResponse({"error": "Invalid request method"}, status=405)
        
@csrf_exempt
def chat_i18n(request):
    with SessionTracker(request) as tracker:
        if request.method == "POST":
            image_file = request.FILES.get('image')
            message = request.POST.get('message', None)
            
            print(f"Received image file: {image_file}")
            if not image_file:
                tracker.set_response_status(400)
                return JsonResponse({"error": "Image file is required"}, status=400)
            
            tracker.set_uploaded_file(image_file)
            
            try:
                response = openai_model.get_response_for_i18n_analysis(image_file, message)
                tracker.set_response_status(200)
                return JsonResponse({"result": response})
            except Exception as e:
                print(f"Error analyzing i18n from image: {e}")
                tracker.set_response_status(500)
                tracker.set_error_message(f"Failed to analyze i18n: {str(e)}")
                return JsonResponse({"error": f"Failed to analyze i18n: {str(e)}"}, status=500)

        elif request.method == "GET":
            tracker.set_response_status(200)
            return JsonResponse({"message": "This API only supports POST requests with an image file."})
        
        else:
            tracker.set_response_status(405)
            return JsonResponse({"error": "Invalid request method"}, status=405)
    
@csrf_exempt
def demo_vision(request):
    if request.method == "POST" and request.FILES.get("file"):
        image_file = request.FILES["file"]
        message = request.POST.get('message', None)
        print('image_file', image_file.name)
        print('message is ',message)
        if not image_file:
            return JsonResponse({"error": "No image file provided"}, status=400)

        # Ensure the images directory exists
        images_dir = "src/images"
        os.makedirs(images_dir, exist_ok=True)
        
        temp_path = os.path.join(images_dir, image_file.name)
        with open(temp_path, "wb") as f:
            for chunk in image_file.chunks():
                f.write(chunk)

        # response = openai_chat_image.get_gpt_vision_response(temp_path, message)
        response = "Vision analysis temporarily disabled"

        return JsonResponse({"result": response})

    elif request.method == "GET":
        return JsonResponse({"message": "This API only supports POST requests with an image file."})

    else:
        return JsonResponse({"error": "Invalid request method"}, status=405)
    
def get_message(request):
    if request.method == "POST":
        message = request.POST.get('message', None)
        print(f"the data from client is",message)
        reponse = openai_model.get_message_response(message)
        return JsonResponse({"result": reponse})
    elif request.method == "GET":
        return JsonResponse({"message": "This API only supports POST requests with message."})
    else:
        return JsonResponse({"error": "Invalid request method"}, status=405)

@csrf_exempt
def analyze_image_comparison(request):
    with SessionTracker(request) as tracker:
        print("request.POST:", request.POST)
        if request.method == "POST":
            reference_image = request.FILES.get('reference_image')
            target_image = request.FILES.get('target_image')
            message = request.POST.get('message', None)
            
            print(f"the data from client is reference_image: {reference_image}, target_image: {target_image}, message: {message}")
            if not reference_image:
                tracker.set_response_status(400)
                return JsonResponse({"error": "reference image URL is required"}, status=400)
            if not target_image:
                tracker.set_response_status(400)
                return JsonResponse({"error": "target image URL is required"}, status=400)
            
            # Set both uploaded files for tracking
            tracker.set_uploaded_files([reference_image, target_image])
            
            try:
                response = openai_model.get_response_from_image_comparison(reference_image, target_image, message)
                tracker.set_response_status(200)
                return JsonResponse({"result": response})
            except Exception as e:
                tracker.set_response_status(500)
                tracker.set_error_message(str(e))
                return JsonResponse({"error": str(e)}, status=500)

        elif request.method == "GET":
            tracker.set_response_status(200)
            return JsonResponse({"message": "This API only supports POST requests with image comparison."})
        
        else:
            tracker.set_response_status(405)
            return JsonResponse({"error": "Invalid request method"}, status=405) 

@csrf_exempt
def analyze_image(request):
    with SessionTracker(request) as tracker:
        if request.method == "POST":
            image_file = request.FILES.get('image')
            message = request.POST.get('message', None)
            
            print(f"Received image file: {image_file}")
            if not image_file:
                tracker.set_response_status(400)
                return JsonResponse({"error": "Image file is required"}, status=400)
            
            tracker.set_uploaded_file(image_file)
            
            try:
                response = openai_model.get_response_from_analyze_image(image_file, message)
                tracker.set_response_status(200)
                return JsonResponse({"result": response})
            except Exception as e:
                print(f"Error extracting text from image: {e}")
                tracker.set_response_status(500)
                tracker.set_error_message(f"Failed to extract text: {str(e)}")
                return JsonResponse({"error": f"Failed to extract text: {str(e)}"}, status=500)

        elif request.method == "GET":
            tracker.set_response_status(200)
            return JsonResponse({"message": "This API only supports POST requests with an image file."})
        
        else:
            tracker.set_response_status(405)
            return JsonResponse({"error": "Invalid request method"}, status=405)
        
@csrf_exempt
def analyze_image_upload(request):
    from gpt_gateway.utils.session_tracker import SessionTracker
    
    with SessionTracker(request) as tracker:
        if request.method == "POST":
            image_file = request.FILES.get('image')
            message = request.POST.get('message', None)
            
            print(f"Received image file: {image_file}")
            if not image_file:
                tracker.set_response_status(400)
                return JsonResponse({"error": "Image file is required"}, status=400)
            
            # Set the uploaded file for tracking
            tracker.set_uploaded_file(image_file)
            
            try:
                response = openai_model.get_response_from_analyze_image(image_file, message)
                tracker.set_response_status(200)
                return JsonResponse({"result": response})
            except Exception as e:
                print(f"Error extracting text from image: {e}")
                tracker.set_response_status(500)
                tracker.set_error_message(f"Failed to extract text: {str(e)}")
                return JsonResponse({"error": f"Failed to extract text: {str(e)}"}, status=500)

        elif request.method == "GET":
            tracker.set_response_status(200)
            return JsonResponse({"message": "This API only supports POST requests with an image file."})
        
        else:
            tracker.set_response_status(405)
            return JsonResponse({"error": "Invalid request method"}, status=405)


@csrf_exempt
def extract_text_from_image(request):
    from gpt_gateway.utils.session_tracker import SessionTracker
    
    with SessionTracker(request) as tracker:
        if request.method == "POST":
            image_file = request.FILES.get('image')
            
            print(f"Received image file: {image_file}")
            if not image_file:
                tracker.set_response_status(400)
                return JsonResponse({"error": "Image file is required"}, status=400)
            
            # Set the uploaded file for tracking
            tracker.set_uploaded_file(image_file)
            
            try:
                response = openai_model.get_text_from_image(image_file)
                tracker.set_response_status(200)
                return JsonResponse({"result": response})
            except Exception as e:
                print(f"Error extracting text from image: {e}")
                tracker.set_response_status(500)
                tracker.set_error_message(f"Failed to extract text: {str(e)}")
                return JsonResponse({"error": f"Failed to extract text: {str(e)}"}, status=500)

        elif request.method == "GET":
            tracker.set_response_status(200)
            return JsonResponse({"message": "This API only supports POST requests with an image file."})
        
        else:
            tracker.set_response_status(405)
            return JsonResponse({"error": "Invalid request method"}, status=405)

@csrf_exempt
def analyze_performance(request):
    """
    Analyze performance data from markdown file or content
    """
    with SessionTracker(request) as tracker:
        if request.method == "POST":
            # Method 1: Upload performance report file
            performance_file = request.FILES.get('performance_file')
            if performance_file:
                tracker.set_uploaded_file(performance_file)
                try:
                    performance_content = performance_file.read().decode('utf-8')
                    response = openai_model.get_response_for_pf(performance_content)
                    print(f"Performance analysis response: {response}")
                    tracker.set_response_status(200)
                    return HttpResponse(response, content_type='text/plain; charset=utf-8')
                except Exception as e:
                    tracker.set_response_status(400)
                    tracker.set_error_message(str(e))
                    return HttpResponse(f"Error processing performance file: {str(e)}", status=400)
            
            # Method 2: Submit performance data directly
            performance_content = request.POST.get('performance_content')
            if performance_content:
                try:
                    response = openai_model.get_response_for_pf(performance_content)
                    print(f"Performance analysis response: {response}")
                    tracker.set_response_status(200)
                    return HttpResponse(response, content_type='text/plain; charset=utf-8')
                except Exception as e:
                    tracker.set_response_status(400)
                    tracker.set_error_message(str(e))
                    return HttpResponse(f"Error processing performance content: {str(e)}", status=400)
            
            tracker.set_response_status(400)
            return JsonResponse({"error": "No performance file or content provided"}, status=400)
        
        elif request.method == "GET":
            tracker.set_response_status(200)
            return JsonResponse({"message": "This API supports POST requests with performance data file or content for analysis."})
        
        else:
            tracker.set_response_status(405)
            return JsonResponse({"error": "Invalid request method"}, status=405)
