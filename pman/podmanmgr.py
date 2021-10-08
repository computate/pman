"""
Podman cluster manager module that provides functionality to schedule
jobs (short-lived services) as well as manage their state in the cluster.
"""

import os
import logging
import podman
from podman.domain.images import Image
from .abstractmgr import AbstractManager, ManagerException


class PodmanManager(AbstractManager):

    def __init__(self, config_dict=None):
        super().__init__(config_dict)

        self.podman_client = podman.PodmanClient(base_url='tcp://%s:%s' % (os.getenv('PODMAN_IP_ADDRESS'), os.getenv('PODMAN_TCP_PORT')))

    def schedule_job(self, image, command, name, resources_dict, mountdir=None):
        """
        Schedule a new job and return the job (podman service) object.
        """
        restart_policy = {'Name': 'no', 'MaximumRetryCount':0}
        mounts = []
        if mountdir is not None:
            mounts.append({'source': mountdir, 'destination': '/share', 'type': 'bind', 'options': ['rw']})
        try:
            logging.info(' create container image="%s", command="%s", name="%s", mounts=%s, restart_policy=%s' % (image, command, name, mounts, restart_policy))
            job = self.podman_client.containers.create(image, command.split(' '), name=name, mounts=mounts, restart_policy=restart_policy, tty=True)
        except Exception as e:
                status_code = 503 if e.response.status_code == 500 else e.response.status_code
                raise ManagerException(str(e), status_code=status_code)
        return job

    def get_job(self, name):
        """
        Get a previously scheduled job object.
        """
        try:
            job = self.podman_client.containers.get(name)
        except Exception as e:
            raise ManagerException(str(e), status_code=400)
        return job

    def get_job_logs(self, job):
        """
        Get the logs from a previously scheduled job object.
        """
        return ''.join([l.decode() for l in job.logs(stdout=True, stderr=True)])

    def get_job_info(self, job):
        """
        Get the job's info for a previously scheduled job object.
        """
        info = super().get_job_info(job)
        info['status'] = 'notstarted'
        info['message'] = 'task not available yet'

        task = self.get_job_task(job)
        if task:
            status = 'undefined'
            state = task['State']['Status']
            if state in ('new', 'pending', 'assigned', 'accepted', 'preparing',
                         'starting'):
                status = 'notstarted'
            elif state == 'running':
                status = 'started'
            elif state == 'failed':
                status = 'finishedWithError'
            elif state == 'complete':
                status = 'finishedSuccessfully'

            info['name'] = job.name
            info['image'] = task['Spec']['ContainerSpec']['Image']
            info['cmd'] = ' '.join(task['Spec']['ContainerSpec']['Command'])
            info['timestamp'] = task['Status']['Timestamp']
            info['message'] = task['Status']['Message']
            info['status'] = status
        return info

    def remove_job(self, job):
        """
        Remove a previously scheduled job.
        """
        job.remove()

    def get_job_task(self, job):
        """
        Get the job's task for a previously scheduled job object.
        """
        return job.inspect()
