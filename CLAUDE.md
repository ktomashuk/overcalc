**# Project Context**

**## Overview**
An overengineered calculator. The project is designed to help prepare for job interviews by using different technologies.

**## Technology Stack**
- Python
- FastAPI
- SQLAlchemy
- PostgreSQL
- Docker
- Apache Kafka
- React

**## Architecture**
The backend uses Domain-Driven Design patterns. Every module has four layers:
- presentation/ - Entry points (endpoints, subscribers, clients, cron jobs)
- application/ - Business logic (use cases)
- infrastructure/ - Integration with external systems (DB, Kafka)
- domain/ - Domain model (aggregates, entities, domain events)

Dependency rules between layers:
- presentation can import domain, application, infrastructure
- application can import domain
- infrastructure can import domain, application.interfaces
- domain cannot import any other layer

Detailed, binding rules (per-layer responsibilities, allowed libraries, module/service boundaries,
naming, testing, enforcement) live in ARCHITECTURE.md:

@ARCHITECTURE.md
