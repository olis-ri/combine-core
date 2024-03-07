import logging

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required

from core.models import CombineBackgroundTask, CombineJob

from .view_helpers import breadcrumb_parser

LOGGER = logging.getLogger(__name__)

@login_required
def bg_tasks(request):
    LOGGER.debug('retrieving background tasks')

    # update all tasks not marked as complete
    nc_tasks = CombineBackgroundTask.objects.filter(completed=False)
    for task in nc_tasks:
        task.update()

    return render(request, 'core/bg_tasks.html', {
        'breadcrumbs': breadcrumb_parser(request)
    })

@login_required
def bg_tasks_delete_all(request):
    LOGGER.debug('deleting all background tasks')

    # delete all Combine Background Tasks
    cts = CombineBackgroundTask.objects.all()
    for combine_task in cts:
        combine_task.delete()

    return redirect('bg_tasks')

@login_required
def bg_task(request, task_id):
    # get task
    combine_task = CombineBackgroundTask.objects.get(pk=int(task_id))
    LOGGER.debug('retrieving task: %s', combine_task)

    # include job if mentioned in task params
    if 'job_id' in combine_task.task_params:
        cjob = CombineJob.get_combine_job(combine_task.task_params['job_id'])
    else:
        cjob = None

    return render(request, 'core/bg_task.html', {
        'ct': combine_task,
        'cjob': cjob,
        'breadcrumbs': breadcrumb_parser(request)
    })

@login_required
def bg_task_delete(request, task_id):
    # get task
    combine_task = CombineBackgroundTask.objects.get(pk=int(task_id))
    LOGGER.debug('deleting task: %s', combine_task)

    combine_task.delete()

    return redirect('bg_tasks')

@login_required
def bg_task_cancel(request, task_id):
    # get task
    combine_task = CombineBackgroundTask.objects.get(pk=int(task_id))
    LOGGER.debug('cancelling task: %s', combine_task)

    # cancel
    combine_task.cancel()

    return redirect('bg_tasks')
