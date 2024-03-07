import logging
import json

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required


from core import forms, tasks
from core.models import Organization, RecordGroup, CombineBackgroundTask, GlobalMessageClient

from .view_helpers import breadcrumb_parser

LOGGER = logging.getLogger(__name__)

@login_required
def organizations(request):
    """
        View all Organizations
        """

    # show organizations
    if request.method == 'GET':
        LOGGER.debug('retrieving organizations')

        # get all organizations
        orgs = Organization.objects.exclude(for_analysis=True).all()

        # render page
        return render(request, 'core/organizations.html', {
            'orgs': orgs,
            'breadcrumbs': breadcrumb_parser(request)
        })

    # create new organization
    if request.method == 'POST':
        # create new org
        LOGGER.debug(request.POST)
        form = forms.OrganizationForm(request.POST)
        new_org = form.save()

        return redirect('organization', org_id=new_org.id)

@login_required
def organization(request, org_id):
    """
        Details for Organization
        """

    # get organization
    org = Organization.objects.get(pk=org_id)

    # get record groups for this organization
    record_groups = RecordGroup.objects.filter(
        organization=org).exclude(for_analysis=True)

    # render page
    return render(request, 'core/organization.html', {
        'org': org,
        'record_groups': record_groups,
        'breadcrumbs': breadcrumb_parser(request)
    })

@login_required
def organization_delete(request, org_id):
    """
        Delete Organization
        Note: Through cascade deletes, would remove:
                - RecordGroup
                        - Job
                                - Record
        """

    # get organization
    org = Organization.objects.get(pk=org_id)

    # set job status to deleting
    org.name = "%s (DELETING)" % org.name
    org.save()

    # initiate Combine BG Task
    combine_task = CombineBackgroundTask(
        name='Delete Organization: %s' % org.name,
        task_type='delete_model_instance',
        task_params_json=json.dumps({
            'model': 'Organization',
            'org_id': org.id
        })
    )
    combine_task.save()

    # run celery task
    bg_task = tasks.delete_model_instance.delay('Organization', org.id, )
    LOGGER.debug('firing bg task: %s', bg_task)
    combine_task.celery_task_id = bg_task.task_id
    combine_task.save()

    return redirect('organizations')

@login_required
def organization_run_jobs(request, org_id):
    org = Organization.objects.get(pk=int(org_id))
    jobs = org.all_jobs()
    tasks.rerun_jobs(jobs)
    gmc = GlobalMessageClient(request.session)
    gmc.add_gm({
        'html': '<strong>Preparing to Rerun Job(s):</strong><br>%s' % '<br>'.join(
            [str(j.name) for j in jobs]),
        'class': 'success'
    })
    return redirect('organizations')

@login_required
def organization_stop_jobs(request, org_id):
    org = Organization.objects.get(pk=int(org_id))
    jobs = org.all_jobs()
    for job in jobs:
        LOGGER.debug('stopping Job: %s', job)
        job.stop_job()

    gmc = GlobalMessageClient(request.session)
    gmc.add_gm({
        'html': '<p><strong>Stopped Job(s):</strong><br>%s</p>' % (
            '<br>'.join([j.name for j in jobs])),
        'class': 'danger'
    })

    return redirect('organizations')
