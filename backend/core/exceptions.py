"""
Custom exception handlers for the project
"""
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
import logging

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    """
    Custom exception handler that provides consistent error responses
    """
    # Call REST framework's default exception handler first
    response = exception_handler(exc, context)

    if response is not None:
        # Customize the response data
        custom_response_data = {
            'code': response.status_code,
            'message': str(exc),
            'errors': response.data
        }
        response.data = custom_response_data
    else:
        # Handle non-DRF exceptions
        logger.error(f"Unhandled exception: {exc}", exc_info=True)
        custom_response_data = {
            'code': status.HTTP_500_INTERNAL_SERVER_ERROR,
            'message': 'Internal server error',
            'errors': str(exc)
        }
        response = Response(custom_response_data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return response
