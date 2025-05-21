#!/bin/bash
kubectl get pods --no-headers=true | awk '/0/{print $1}' | xargs kubectl delete pod
