# Reference Architecture: AI-Driven ITSM Pipeline

## 1. Executive Summary

This document outlines a fully automated, agentic IT Service Management (ITSM) workflow. By integrating **Kiro** (Observability Agent) and **Amazon Q** (Remediation Agent), this architecture transitions our operations from manual ticket triaging to automated, code-aware remediation and documentation.

## 2. Architecture Diagram

```mermaid
graph LR
    %% 1. Ingestion
    subgraph Ingestion
        Splunk[Splunk]
        Datadog[Datadog]
        S3[(AWS S3 Bucket)]
        Kafka{{Kafka Fast Stream}}
    end

    Splunk -->|Send Logs| S3
    Datadog -->|Send Logs| S3
    Splunk -.->|Fast stream| Kafka
    Datadog -.->|Fast stream| Kafka

    %% 2. Detection
    subgraph Detection
        Kiro[Kiro Agent]
    end

    S3 -->|Read Logs| Kiro
    Kiro -->|Create Ticket| Jira[Jira Ticket]

    %% 3. Analysis
    subgraph Analysis
        Q[Amazon Q Agent]
        GitHub[(Source Code)]
        Docs[(Runbooks)]
    end

    Jira -->|Read Ticket| Q
    Q <-->|Read Code| GitHub
    Q <-->|Read Docs| Docs

    %% 4. Remediation & Routing
    subgraph Remediation
        Check{Is fix easy?}
        Auto[Auto Deploy]
        Human[Dev Approval]
    end

    Q --> Check
    Check -->|Yes| Auto
    Check -->|No| Human

    %% 5. Reporting
    subgraph Reporting
        Chalk[Chalkpage Wiki]
    end

    Kiro -->|Log Issue| Chalk
    Q -->|Log Fix| Chalk
    Human -->|Log Notes| Chalk
    Auto -->|Log Status| Chalk
```
