## Jobs

[Jobs](https://kubernetes.io/docs/concepts/workloads/controllers/job/), like many other Kubernetes primitives, create pods. However, in contrast to your typical pods, these pods are meant for operations where the operation is expected to eventually terminate. For example, you could create a Job to run a database backup using a one-off pod. When the database backup has been generated and stored somewhere by the pod, the pod is terminated. Jobs can also be run in parallel, for example to unload a work queue.

### A flaky task

For demonstration purposes, let's create [a slightly flaky Python application](./app/app.py), which we will run in our Job:

```python
import sys
import random
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def perform_flaky_task() -> None:
    """Execute task which might fail or not"""
    if random.random() < 0.4:
        logging.info("Task succeeded")
        sys.exit(0)
    logging.error("Task failed")
    sys.exit(1)


if __name__ == "__main__":
    perform_flaky_task()

```

When executed, this application will randomly either fail or succeed. If it fails, it will log an error and the process return code is 1. If it on the other hand succeeds, the return code is 0.

### Publishing our application

Now that we have our application defined, let's write [a simple do-not-use-this-in-production Dockerfile](./app/Dockerfile) for it:

```dockerfile
FROM python:3.9-alpine

WORKDIR /usr/src/app

COPY app.py .

ENTRYPOINT ["python", "app.py"]
```

If you haven't already got a k3d cluster up and running, create one once again:

```shell
$ k3d cluster create my-cluster --servers 1 --agents 1 --registry-create
```

Then build and publish your container image to the [container registry maintained by k3d](https://k3d.io/usage/guides/registries/#using-a-local-registry):

```shell
$ docker build -t k3d-my-cluster-registry:50664/flaky-app:0.1 .
$ docker push k3d-my-cluster-registry:50664/flaky-app:0.1
```

And now we're ready to create a Job!

### Executing a Job

Our simple example Job looks like this:

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: example-job
spec:
  template:
    spec:
      containers:
        - name: flaky-app
          image: k3d-my-cluster-registry:50664/flaky-app:0.1
      restartPolicy: never
  backoffLimit: 10
```

Every time our application fails, i.e. returns a non-zero exit code, a new pod is started. This process is repeated until either our application successfully terminates, or 10 attempts (and thus pods) have been made. So let's test it out:

```shell
$ kubectl apply -f job.yaml
```

Now you should be able to see the job:

```
$ kubectl get jobs

NAME          COMPLETIONS   DURATION   AGE
example-job   1/1           3m39s      6m44s
```

Depending how many times the application failed, you should also see a number of pods, as the pods executed by the job are left behind for further inspection:

```
$ kubectl get pods

NAME                READY   STATUS      RESTARTS   AGE
example-job-nh95r   0/1     Error       0          8m12s
example-job-qnkmh   0/1     Error       0          8m5s
example-job-tf27z   0/1     Error       0          7m55s
example-job-8l55v   0/1     Error       0          7m15s
example-job-j7wdp   0/1     Completed   0          4m35s
```

This time the application failed four times, and so we have four failed pods and a single succesfully completed one. You can take a closer look at the logs emitted by one of the failed pods:

```
$ kubectl logs example-job-8l55v

ERROR:root:Task failed
```

You can also inspect the job itself to see more or less the same:

```
$ kubectl describe jobs example-job | grep -A 10 Events

Events:
  Type    Reason            Age   From            Message
  ----    ------            ----  ----            -------
  Normal  SuccessfulCreate  20m   job-controller  Created pod: example-job-nh95r
  Normal  SuccessfulCreate  20m   job-controller  Created pod: example-job-qnkmh
  Normal  SuccessfulCreate  19m   job-controller  Created pod: example-job-tf27z
  Normal  SuccessfulCreate  19m   job-controller  Created pod: example-job-8l55v
  Normal  SuccessfulCreate  16m   job-controller  Created pod: example-job-j7wdp
  Normal  Completed         16m   job-controller  Job completed
```

Once you've done some digging and are happy with the outcome of your job, you can delete it:

```
$ kubectl delete jobs example-job

job.batch "example-job" deleted
```

After this the pods will be automatically also deleted.
