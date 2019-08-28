# kondunite

[![PyPI version](https://badge.fury.io/py/kondunite.svg)](https://badge.fury.io/py/kondunite)

**Kubernetes Conditional Manifests Unifier**

The tool is used to unify Kubernetes manifests targeting a specific release, by using hints in the manifest files.

Currently only yaml manifests are supported.

Tool is written and tested only in Python 3.7

## Install

You can run the following out of any venv. Just make sure you separately installed the stuff in requirements.txt outside the venv as well.

```bash
pip install --upgrade kondunite
```

## Usage

Terminology - 
* target - a platform for which we might want to apply the manifests to. i.e GKE.
* repl - short for [replicated](https://help.replicated.com/).

```text
Usage: kondunite [OPTIONS] DIRECTORY

Options:
  --no-recurse          Do not recurse manifests directory
  -t, --target TEXT     Conditional target for unification  [required]
  -i, --img TEXT        One or more tag to specific images, provide values in
                        the forms of 'image-name:tag', i.e
                        gcr.io/company/server:1.0
  -b, --repl-base TEXT  Base replicated yaml definition (for '#kind:
                        replicated' section), defaults to
                        <directory>/replicated_base.yaml
  -o, --output TEXT     File to write the unified yaml to, defaults to
                        <target>.yaml
  -r, --repl            Plot output for a replicated release (with '# kind:
                        scheduler-kubernetes' annotations)
  --repl-registry TEXT  One or more docker registries defined in your
                        Replicated settings in the form of endpoint:name, i.e
                        gcr.io/company
  --help                Show this message and exit.
```

Where `DIRECTORY` is the path to a directory containing the Kubernetes manifests.

Currently all filenames across all subdirectories must be unique. Only one of the file instances will be picked if this assumption does not hold.

### Options

* `--img`: Used to override image tags in the manifests. Can also be used if the manifests contain only placeholder tags.
* `--repl-base`: File containing the basic replicated release file definitions. See [documentation](https://help.replicated.com/docs/kubernetes/packaging-an-application/yaml-format/).
* `--repl-registry`: Specify the Docker registries to be configured in the replicated release file. See [documentation](https://help.replicated.com/docs/kubernetes/getting-started/docker-registries/).

### Examples

```bash
kondunite --target gke -i neo4j:lat3st -i gcr.io/apiiro/lim/api:1.0 ./k8s
kondunite --target repl -i neo4j:late5t -i gcr.io/apiiro/lim/api:1.0 --repl --repl-registry gcr.io/apiiro ./k8s
```

For more detailed examples see [examples](https://github.com/apiiro/kondunite/tree/master/examples).

## Manifests Hints

Some hints could be injected to the Kubernetes manifests to utilize the power of this tool.

Noe the hints will make the manifests syntactically invalid by Kubernetes definitions and must be parse by this tool to be applicable.

### targetsOnly

Specify at manifest top level that it only targets a specific platform.

```yaml
targetsOnly: <target>
```

For example:

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
targetsOnly: gke
metadata:
  name: pvc
spec:
  accessModes:
    - ReadWriteMany
  storageClassName: ""
  resources:
    requests:
      storage: 17Gi
```

### dependencies

Specify apply-time dependencies for the manifests, meaning which manifest should be applied before which. You can specify one or more.

In case of a circular dependency a `toposort.CircularDependencyError` will be raised with a descriptive message.

It is assumed that manifests in the same file should maintain their definition order.

```yaml
dependencies:
  - filename1.yaml
  - filename2.yaml
```

Currently only filenames are supported (not paths). So if the files in dependency reside in different directories they could still be declared as dependent without specifying their relation. Note recurring filenames are currently not supported. 

For example:

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
dependencies:
  - nfs.yaml
  - pv.yaml
metadata:
  name: pvc
spec:
  accessModes:
    - ReadWriteMany
  storageClassName: ""
  resources:
    requests:
      storage: 17Gi
```

### `-<target>` yaml node suffix

If any node in a manifest is named with a `-<target>` suffix, it will be filtered out if the target mismatches the requested target.

The feature is only supported for dict or list nodes, meaning not for low level nodes such as strings etc.
Since Kubernetes manifests use only camel casing, a dash character should not appear in any (non low level) node that does not intend to hint on a target.

This hint act similar to `targets_only` hint, however it applies only to a node and not to a whole manifest.

```yaml
<node>-<target>:
    ...
```

For example:

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: pvc
spec:
  accessModes-gke:
    - ReadWriteOnce
  accessModes-repl:
    - ReadWriteMany
  storageClassName: ""
  resources:
    requests-gke:
      storage: 17Gi
    requests-repl:
      storage: 7Gi
```

(Note `accessMode` and `requests` nodes)

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: neo4j
spec:
  strategy:
    type: Recreate
  selector:
    matchLabels:
      app: neo4j
  template:
    metadata:
      labels:
        app: neo4j
    spec:
      containers:
        - name: neo4j
          image: neo4j:latest
          env-repl:
            - name: NEO_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: neo4j
                  key: neo-password
          env-gke:
            - name: NEO_PASSWORD
              value: 'password'
```

(Note `env` node)

## Dev Setup

Only Python3 is supported.

Create a virtualenv: `python3 -m venv ./venv`

And activate it: `source dev.sh`

Install requirements: `pip install -r requirements.txt`

Install package: `pip install --editable .`

## Deployment

Package is deployed using Google Cloud Build. See [cloudbuild.yaml](https://github.com/apiiro/kondunite/tree/master/cloudbuild.yaml).

Any push to `master` branch will trigger a push to pypi if package version was increased.

For a push to any branch, a sanity wheel build will run. 
