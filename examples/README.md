# kondunite - Usage Example

Example is adapted from https://kubernetes.io/docs/tutorials/stateful-application/mysql-wordpress-persistent-volume/

It contains two components - MYSql database and Wordpress server.

The manifests are defined for two targets: GKE (`gke`) and replicated (`repl`), with the intention of using the gke target for managed Kubernetes dpeloyments (such as GKE) and the replicated for on-prem deployments using the Replicated product.

The generated manifests are []() and []().

To generate them yourself:

```bash
kondunite --target gke \
    -i mysql:5.7 \
    --repl-base ./manifests/replicated_base.yaml \
    -o gke.yaml \
    ./manifests

kondunite --target repl \
    -i mysql:5.7 \
    --repl --repl-base ./manifests/replicated_base.yaml \
    -o replicated.yaml \
    ./manifests
```

## Motivation to use two different targets

Why do we need two different targets to begin with? In this example we have a couple of reasons:
* Persistency - While in GKE we use a simple PVC, in Replicated we might want to use Replicated-provided Rook under a shared fs.
* Frontend - We want to expose wordpress service publicly on port 80. In GKE we'd simply used a LoadBalancer. However in Replicated we want to use an Ingress that relies on Replicated-provided Contour.
* Password - In GKE we assume someone already defined the secret for mysql password (its not recommended to store the password in a manifest file). In Replicated we'd use the built in configuration page to let the admin configure the password.
