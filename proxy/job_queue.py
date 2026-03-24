class Job:
    def __init__(self, job_id, func, *args, **kwargs):
        self.job_id = job_id
        self.func = func
        self.args = args
        self.kwargs = kwargs
        self.status = 'pending'

    def run(self):
        self.status = 'running'
        try:
            return self.func(*self.args, **self.kwargs)
        except Exception as e:
            self.status = 'failed'
            raise e
        else:
            self.status = 'completed'

class JobQueue:
    def __init__(self):
        self.queue = []

    def add_job(self, job):
        self.queue.append(job)

    def run_jobs(self):
        for job in self.queue:
            job.run()