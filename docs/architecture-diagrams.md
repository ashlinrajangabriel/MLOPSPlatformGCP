# Developer Platform Architecture Diagrams

## Infrastructure Overview

```mermaid
graph TB
    subgraph "Google Cloud Platform"
        subgraph "VPC Service Controls Perimeter"
            subgraph "GKE Cluster"
                subgraph "System Namespace"
                    ARGO[ArgoCD]
                    JHUB[JupyterHub]
                    PROM[Prometheus]
                    GRAF[Grafana]
                end

                subgraph "User Namespace"
                    VSCODE[VSCode Pods]
                    JL[JupyterLab Pods]
                    PVC[(User PVCs)]
                end
            end

            AR[(Artifact Registry)]
            GCS[(Cloud Storage)]
        end

        IAM[IAM & Admin]
        GAUTH[Google Auth]
    end

    subgraph "External Services"
        GH[GitHub]
        DNS[Cloud DNS]
        OIDC[OIDC Provider]
    end

    %% Infrastructure Connections
    GH -->|GitOps| ARGO
    ARGO -->|Deploys| JHUB
    JHUB -->|Spawns| VSCODE
    JHUB -->|Spawns| JL
    VSCODE --> PVC
    JL --> PVC
    PVC -->|Versioning| GCS
    IAM -->|Auth| GAUTH
    GAUTH -->|OAuth| OIDC
    DNS -->|Routes| JHUB
```

## Data Flow Architecture

```mermaid
sequenceDiagram
    participant User
    participant DNS as Cloud DNS
    participant Auth as Google Auth
    participant Hub as JupyterHub
    participant K8s as GKE
    participant Storage as GCS + PVC

    User->>DNS: Access jupyter.domain.com
    DNS->>Hub: Route Request
    Hub->>Auth: Authenticate (OIDC)
    Auth-->>Hub: User Info + Groups
    Hub->>K8s: Spawn User Pod
    K8s->>Storage: Mount User PVC
    Storage-->>K8s: PVC Ready
    K8s-->>Hub: Pod Ready
    Hub-->>User: Redirect to Environment
```

## Storage Architecture

```mermaid
graph TB
    subgraph "User Workspace"
        WS[Workspace Pod]
        subgraph "Storage Layer"
            PVC[(PVC)]
            GCSF[GCSFuse Mount]
            GIT[Git Workspace]
        end
    end

    subgraph "Google Cloud Storage"
        GCSB[GCS Bucket]
        subgraph "Lifecycle Management"
            ST[Standard Storage]
            NL[Nearline - 30d]
            CL[Coldline - 90d]
            AL[Archive - 365d]
        end
    end

    WS -->|R/W| PVC
    PVC -->|Version History| GCSF
    GCSF -->|Sync| GCSB
    GIT -->|Code Version| PVC
    GCSB --> ST
    ST --> NL
    NL --> CL
    CL --> AL
```

## Security Architecture

```mermaid
graph TB
    subgraph "External Access"
        USER[User]
        ADMIN[Admin]
    end

    subgraph "Security Controls"
        WAF[Cloud Armor WAF]
        GAUTH[Google Auth]
        RBAC[RBAC Policies]
    end

    subgraph "VPC Service Controls"
        subgraph "GKE Security"
            BIN[Binary Authorization]
            SCAN[Vulnerability Scanning]
            AUDIT[Audit Logging]
        end

        subgraph "Data Security"
            CRYPT[Encryption]
            BAK[Backups]
            VER[Versioning]
        end
    end

    USER --> WAF
    ADMIN --> WAF
    WAF --> GAUTH
    GAUTH --> RBAC
    RBAC --> BIN
    BIN --> SCAN
    SCAN --> AUDIT
    AUDIT --> CRYPT
    CRYPT --> BAK
    BAK --> VER
```

## Network Architecture

```mermaid
graph TB
    %% External Layer
    CLIENT[Client Browser]
    EXT[External Services]

    %% Load Balancing
    GCLB[Global Load Balancer]
    SSL[SSL Termination]
    CA[Cloud Armor WAF]

    %% Network Components
    ILB[Internal Load Balancer]
    NAT[Cloud NAT]
    INGRESS[Ingress Controller]
    MON[Monitoring Stack]

    %% GKE Components
    JH[JupyterHub]
    VS[VSCode Servers]
    PODS[User Pods]

    %% Storage
    GCS[Cloud Storage]
    REG[Artifact Registry]

    %% Security
    FW[Firewall Rules]
    PSC[Private Service Connect]
    VPC[VPC Service Controls]

    %% Connections - External to Internal
    CLIENT --> GCLB
    EXT --> GCLB
    GCLB --> SSL
    SSL --> CA
    CA --> ILB
    
    %% Internal Traffic Flow
    ILB --> INGRESS
    INGRESS --> JH
    INGRESS --> VS
    JH --> PODS
    VS --> PODS
    
    %% Egress Flow
    PODS --> NAT
    NAT --> EXT
    
    %% Data Access
    PODS --> GCS
    PODS --> REG
    
    %% Security Controls
    FW -.-> ILB
    PSC -.-> GCS
    PSC -.-> REG
    VPC -.-> GCS
    VPC -.-> REG
    
    %% Monitoring
    PODS --> MON

    %% Styling
    classDef external fill:#f9f,stroke:#333
    classDef security fill:#ff9,stroke:#333
    classDef storage fill:#9ff,stroke:#333
    
    class CLIENT,EXT external
    class FW,PSC,VPC security
    class GCS,REG storage
```

## Network Configuration Details

```mermaid
graph TB
    %% VPC and Subnet Definitions
    subgraph VPC["VPC (10.0.0.0/16)"]
        subgraph PUB["Public Subnet (10.0.1.0/24)"]
            NAT[Cloud NAT]
            ILB[Internal Load Balancer]
        end
        
        subgraph PRV["Private GKE Subnet (10.0.2.0/23)"]
            CTRL["Control Plane (10.0.2.0/28)"]
            SYS["System Node Pool (10.0.2.16/28)"]
            WORK["Workload Node Pool (10.0.2.32/27)"]
        end

        subgraph DATA["Data Subnet (10.0.3.0/24)"]
            GCS[Cloud Storage]
            REG[Artifact Registry]
        end
    end

    %% Security Groups/Network Policies
    subgraph SEC["Security Groups"]
        PUB_SG["Public SG<br/>Ingress: 443,80<br/>Egress: ALL"]
        GKE_SG["GKE SG<br/>Ingress: 443,6443,8443<br/>Egress: ALL"]
        DATA_SG["Data SG<br/>Ingress: 443 from GKE<br/>Egress: None"]
    end

    %% Network Policies
    subgraph POL["Network Policies"]
        direction TB
        ING["Ingress Rules<br/>- Allow HTTPS from LB<br/>- Allow internal traffic"]
        EGR["Egress Rules<br/>- Allow DNS (53)<br/>- Allow HTTPS (443)<br/>- Block metadata API"]
    end

    %% Authorized Networks
    subgraph AUTH["Authorized Networks"]
        CORP["Corporate VPN<br/>172.16.0.0/12"]
        MGMT["Management CIDR<br/>192.168.1.0/24"]
    end

    %% Connections and Policies
    PUB_SG -.-> PUB
    GKE_SG -.-> PRV
    DATA_SG -.-> DATA
    
    ING -.-> PRV
    EGR -.-> PRV
    
    CORP --> VPC
    MGMT --> VPC

    %% Styling
    classDef subnet fill:#e6f3ff,stroke:#333
    classDef secgroup fill:#fff2cc,stroke:#333
    classDef policy fill:#d5e8d4,stroke:#333
    classDef auth fill:#ffe6cc,stroke:#333
    
    class PUB,PRV,DATA subnet
    class PUB_SG,GKE_SG,DATA_SG secgroup
    class ING,EGR policy
    class CORP,MGMT auth
```

## Network Access Matrix

```mermaid
graph LR
    %% Components
    subgraph EXTERNAL["External Access"]
        USER[Users]
        API[API Clients]
    end

    subgraph INTERNAL["Internal Components"]
        GKE[GKE Cluster]
        DB[Databases]
        STOR[Storage]
    end

    %% Access Rules
    USER -->|HTTPS 443| GKE
    API -->|HTTPS 443| GKE
    GKE -->|TCP 5432| DB
    GKE -->|HTTPS 443| STOR
    
    %% Deny Rules
    DB x---x EXTERNAL
    STOR x---x EXTERNAL

    %% Styling
    classDef external fill:#f9f,stroke:#333
    classDef internal fill:#9ff,stroke:#333
    classDef deny stroke:#f00,stroke-width:2px
    
    class USER,API external
    class GKE,DB,STOR internal
```

## Network Security Controls

```mermaid
graph TB
    %% Security Layers
    subgraph EDGE["Edge Security"]
        WAF["Cloud Armor WAF<br/>DDoS Protection<br/>Rate Limiting"]
        CERT["SSL/TLS Termination<br/>Managed Certificates"]
    end

    subgraph PERIMETER["Network Perimeter"]
        FW["Firewall Rules<br/>- Allow 443 inbound<br/>- Allow internal traffic<br/>- Deny metadata API"]
        IAP["Identity-Aware Proxy<br/>- User Authentication<br/>- Context-aware access"]
    end

    subgraph INTERNAL["Internal Security"]
        PSP["Pod Security Policies<br/>- No privileged<br/>- Read-only root FS"]
        NP["Network Policies<br/>- Default deny<br/>- Explicit allow"]
    end

    %% Connections
    EDGE --> PERIMETER
    PERIMETER --> INTERNAL

    %% Styling
    classDef edge fill:#f9f,stroke:#333
    classDef perimeter fill:#fff2cc,stroke:#333
    classDef internal fill:#d5e8d4,stroke:#333
    
    class WAF,CERT edge
    class FW,IAP perimeter
    class PSP,NP internal
```

## CI/CD Pipeline Architecture

```mermaid
graph TB
    %% Development Stage
    subgraph DEV["Development"]
        COMMIT[Code Commit]
        PR[Pull Request]
        CODE_REV[Code Review]
    end

    %% CI Pipeline
    subgraph CI["Continuous Integration"]
        LINT[Linting]
        TEST[Unit Tests]
        SCAN["Security Scan<br/>- SAST<br/>- Dependency Check"]
        BUILD["Container Build<br/>- Multi-stage<br/>- Distroless base"]
        SEC_SCAN["Container Scan<br/>- Vulnerability Check<br/>- Image Sign"]
    end

    %% Artifact Management
    subgraph ARTIFACTS["Artifact Management"]
        REG["Artifact Registry<br/>- Container Images<br/>- Helm Charts"]
        SIGN["Cosign Signatures"]
        SBOM["SBOM Storage"]
    end

    %% CD Pipeline
    subgraph CD["Continuous Deployment"]
        MANIFEST["Generate K8s Manifests"]
        VALID["Manifest Validation"]
        ARGOCD["ArgoCD Sync"]
        subgraph DEPLOY["Deployment Stages"]
            DEV_ENV["Dev Environment"]
            STAGE_ENV["Staging Environment"]
            PROD_ENV["Production Environment"]
        end
    end

    %% Post Deployment
    subgraph POST["Post Deployment"]
        HEALTH["Health Checks"]
        METRIC["Metrics Validation"]
        ALERT["Alert Configuration"]
    end

    %% Workflow Connections
    COMMIT --> PR
    PR --> CODE_REV
    CODE_REV --> LINT
    LINT --> TEST
    TEST --> SCAN
    SCAN --> BUILD
    BUILD --> SEC_SCAN
    SEC_SCAN --> REG
    SEC_SCAN --> SIGN
    BUILD --> SBOM
    
    REG --> MANIFEST
    MANIFEST --> VALID
    VALID --> ARGOCD
    
    ARGOCD --> DEV_ENV
    DEV_ENV --> STAGE_ENV
    STAGE_ENV --> PROD_ENV
    
    PROD_ENV --> HEALTH
    HEALTH --> METRIC
    METRIC --> ALERT

    %% Environment Specific Checks
    subgraph ENV_CHECKS["Environment Checks"]
        direction TB
        DEV_CHECK["Dev Checks<br/>- Basic Tests<br/>- Smoke Tests"]
        STAGE_CHECK["Stage Checks<br/>- Integration Tests<br/>- Performance Tests"]
        PROD_CHECK["Prod Checks<br/>- Canary Deploy<br/>- Progressive Rollout"]
    end

    DEV_ENV --> DEV_CHECK
    STAGE_ENV --> STAGE_CHECK
    PROD_ENV --> PROD_CHECK

    %% Security Gates
    subgraph SEC_GATES["Security Gates"]
        direction TB
        CODE_SEC["Code Security<br/>- Secret Detection<br/>- Code Analysis"]
        BUILD_SEC["Build Security<br/>- Base Image CVE<br/>- Dependencies"]
        DEPLOY_SEC["Deploy Security<br/>- RBAC Validation<br/>- Network Policies"]
    end

    SCAN --> CODE_SEC
    BUILD --> BUILD_SEC
    VALID --> DEPLOY_SEC

    %% Styling
    classDef dev fill:#d0f4de,stroke:#333
    classDef ci fill:#fff2cc,stroke:#333
    classDef cd fill:#bde0fe,stroke:#333
    classDef sec fill:#ffd6d6,stroke:#333
    classDef art fill:#ddd6fe,stroke:#333
    
    class COMMIT,PR,CODE_REV dev
    class LINT,TEST,SCAN,BUILD,SEC_SCAN ci
    class MANIFEST,VALID,ARGOCD,DEV_ENV,STAGE_ENV,PROD_ENV cd
    class CODE_SEC,BUILD_SEC,DEPLOY_SEC sec
    class REG,SIGN,SBOM art
```

## CI/CD Metrics and Gates

```mermaid
graph LR
    %% Quality Gates
    subgraph GATES["Quality Gates"]
        COV["Code Coverage<br/>>80%"]
        VULN["Vulnerabilities<br/>Zero Critical"]
        PERF["Performance<br/>P95 < 500ms"]
    end

    %% Metrics
    subgraph METRICS["Key Metrics"]
        DEPLOY["Deployment<br/>Frequency"]
        LEAD["Lead Time<br/>for Changes"]
        MTTR["Mean Time<br/>to Recovery"]
        CFR["Change Failure<br/>Rate"]
    end

    %% Automated Checks
    subgraph CHECKS["Automated Checks"]
        SEC["Security<br/>Compliance"]
        CONF["Configuration<br/>Validation"]
        TEST["Test<br/>Coverage"]
    end

    %% Connections with Conditions
    GATES --> |Pass/Fail|DEPLOY
    METRICS -->|Threshold|CHECKS
    CHECKS -->|Validate|GATES

    %% Styling
    classDef gates fill:#f9f,stroke:#333
    classDef metrics fill:#9ff,stroke:#333
    classDef checks fill:#ff9,stroke:#333
    
    class COV,VULN,PERF gates
    class DEPLOY,LEAD,MTTR,CFR metrics
    class SEC,CONF,TEST checks
``` 