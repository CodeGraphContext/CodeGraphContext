# Kubernetes Deployment for CodeGraphContext

This directory contains Kubernetes manifests for deploying CodeGraphContext.

## Files

- `deployment.yaml` - Main application deployment
- `service.yaml` - Service configuration
- `pvc.yaml` - Persistent Volume Claim for data storage
- `configmap.yaml` - Configuration management
- `neo4j-deployment.yaml` - Optional Neo4j database deployment

## Quick Start

1. **Create namespace:**
   ```bash
   kubectl create namespace codegraphcontext
   ```

2. **Deploy CodeGraphContext:**
   ```bash
   kubectl apply -f k8s/ -n codegraphcontext
   ```

3. **Check status:**
   ```bash
   kubectl get pods -n codegraphcontext
   ```

4. **Access the pod:**
   ```bash
   kubectl exec -it deployment/codegraphcontext -n codegraphcontext -- bash
   ```

## Scaling

To scale the deployment:
```bash
kubectl scale deployment/codegraphcontext --replicas=3 -n codegraphcontext
```

## Monitoring

View logs:
```bash
kubectl logs -f deployment/codegraphcontext -n codegraphcontext
```

## Cleanup

```bash
kubectl delete namespace codegraphcontext
```
