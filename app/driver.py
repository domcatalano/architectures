from os import environ
import ray
import time
import random
import click
from ray.dashboard.modules.job.sdk import JobSubmissionClient
from ray.dashboard.modules.job.common import JobStatus, JobStatusInfo

# define a default cluster environment if deploying a new Anyscale Cluster
# more information on cluster environments can be found here: https://docs.anyscale.com/user-guide/configure/dependency-management/anyscale-environments#creating-a-cluster-environment 
DEFAULT_CLUSTER_ENV = "default_cluster_env_1.11.0_py39"

'''
get_anyscale_address is a helper function to determine the endpoint to use when connecting to the Ray cluster.  

If ANYSCALE_ADDRESS is defined in the environment variables, return the defined address
If RUN_RAY_LOCAL is defined, initialize or connect to a cluster running on the local machine
If the application stage is TEST (via environment variables) or variable, create or connect to a TEST cluster

Otherwise, create or connect to a cluster in Anyscale
'''
def get_anyscale_address(stage=None):
    if "ANYSCALE_ADDRESS" in environ:
        return environ["ANYSCALE_ADDRESS"]

    anyscale_env = "dev" if "ANYSCALE_ENVIRONMENT" not in environ else environ["ANYSCALE_ENVIRONMENT"]
    run_local = True if "RUN_RAY_LOCAL" in environ and environ["RUN_RAY_LOCAL"] == "True" else False

    if stage == "LOCAL" or run_local:
        return None
    elif stage == "TEST" or anyscale_env == "TEST":
        return f"anyscale://app-{anyscale_env}-tests"
    else:
        return f"anyscale://app-{anyscale_env}"

class RayEntryPoint:
    """
        A driver class that encapsulates interaction with the ray cluster.  
        On initialization, the cluster is created or connected.  
        A remote actor is also instantiated, which contains the remote methods 
        that will be called via this entry point class
    """
    def __init__(self, url=None):
        self.initialized = False
        self.initialize(url)

    def initialize(self, url=None):
        if (not(self.initialized)):
            self.jobs = []

            # check if url is None. if None, connect to the Ray cluster locally
            if url is None:
                runtime_information = ray.init(ignore_reinit_error=True)
                self.url = runtime_information['webui_url']
                self.client = JobSubmissionClient(self.url)

            else:
                self.url = url

                try:
                    self.client = JobSubmissionClient(url)
                except click.exceptions.ClickException:
                    # if the cluster is not running, Ray JobSubmissionClient cannot be created.
                    CLUSTER_ENV = DEFAULT_CLUSTER_ENV if "CLUSTER_ENV" not in environ else environ["CLUSTER_ENV"] 
                    ray.init(url, cluster_env=CLUSTER_ENV)
                    self.client = JobSubmissionClient(url)

        self.initialized = True

    def execute(self):
        """Kicks off the remote task.
        Makes sure not to block with any calls to ray.get.
        """
        job_id = self.client.submit_job(
            entrypoint="python app/ray_impl/script.py",
            # Working dir
            runtime_env={
                "working_dir": "./",
                "pip": ["requests==2.26.0"],
                "excludes":["tests"]
                }
            )
        self.jobs.append(job_id)

    def respond(self):
        """Fetch the results from a job.
        This naive approach always returns the status of the first-submitted job.
        If it is complete, it returns the results and pops that job off the stack.
        """
        if (len(self.jobs)==0):
            return "No Job Running"
        else:
            job_id = self.jobs[0]
            status = (self.client.get_job_status(job_id)).status

            if (status in {JobStatus.SUCCEEDED, JobStatus.FAILED}):
                self.jobs.pop(0)
                return self.client.get_job_logs(job_id)
            else:
                return status, job_id

    def cleanup(self):
        ray.kill(self.actor)

if (__name__ == "__main__"):
    entry_point = RayEntryPoint(get_anyscale_address="LOCAL")
    entry_point.execute()
    print(entry_point.respond())
    time.sleep(5)
    print(entry_point.respond())
