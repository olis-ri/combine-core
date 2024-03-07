import sys
import traceback

from django.shortcuts import render

from core.models import ErrorReport

import logging
import traceback

LOGGER = logging.getLogger(__name__)

class ErrorMiddleware():
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        return response

    @staticmethod
    def process_exception(request, exception):
        LOGGER.debug(traceback.print_exc())
        report = ErrorReport.create(exception)
        report.save()
        LOGGER.debug(traceback.print_exception(*sys.exc_info()))
        return render(request, 'core/error.html', {'report': report})
