# Mermaid Diagrams Guide

## Overview

This document contains 10 comprehensive mermaid diagrams that visualize the Master's Navigation Audit Alert System architecture. The diagrams are organized to show both **reusable infrastructure** (shared across all alert types) and **alert-specific implementation** (Masters Navigation Audit).

## How to View the Diagrams

### Option 1: GitHub/GitLab
- Push `masters_navigation_audit_diagrams.md` to your repository
- GitHub and GitLab automatically render mermaid code blocks

### Option 2: VS Code
- Install the "Markdown Preview Mermaid Support" extension
- Open the .md file and use the preview pane

### Option 3: Online Editors
- Copy diagram code to https://mermaid.live/
- Or use https://mermaid-js.github.io/mermaid-live-editor/

### Option 4: Command Line
- Install mermaid-cli: `npm install -g @mermaid-js/mermaid-cli`
- Generate images: `mmdc -i masters_navigation_audit_diagrams.md -o diagrams/`

## Diagram Index

### 1. High-Level System Architecture
**Purpose**: Bird's-eye view of the entire system  
**Shows**: 
- Entry point (main.py)
- Core infrastructure (config, scheduler, tracker, base alert)
- Notification layer (email sender, formatters)
- Alert implementation (Masters Navigation Audit)
- Database layer (db_utils, PostgreSQL, SSH tunnel)
- Data storage (logs, tracking file, health status)

**Use this when**:
- Explaining the system to new developers
- Understanding how components are initialized
- Seeing the separation between reusable and alert-specific code

**Color coding**:
- 🟦 Blue: Entry point
- 🟨 Yellow: Core infrastructure (reusable)
- 🟩 Green: Notification layer (reusable)
- 🟥 Red: Alert-specific implementation

---

### 2. Core Infrastructure Class Diagram
**Purpose**: Detailed view of reusable components  
**Shows**: 
- AlertConfig: Centralized configuration management
- AlertScheduler: Scheduling system with multiple modes
- EventTracker: Duplicate prevention and tracking
- BaseAlert: Abstract base class for all alerts
- EmailSender: SMTP email handling
- HTMLFormatter/TextFormatter: Email content generation

**Use this when**:
- Understanding the interface between core and alerts
- Creating a new alert type (inherit from BaseAlert)
- Modifying core infrastructure
- Understanding configuration flow

**Key relationships**:
- AlertConfig creates and injects runtime objects
- BaseAlert depends on all core components
- AlertScheduler orchestrates alert execution

---

### 3. Alert-Specific Implementation
**Purpose**: Shows how Masters Navigation Audit extends the base system  
**Shows**:
- MastersNavigationAuditAlert class
- Inheritance from BaseAlert
- Implementation of abstract methods
- Integration with db_utils
- SQL query structure

**Use this when**:
- Creating a new alert (use as template)
- Understanding how to implement abstract methods
- Seeing what needs to change for a new alert type
- Understanding SQL query requirements

**Key points**:
- Only 6 methods need implementation for a new alert
- SQL query is externalized to queries/ directory
- Alert-specific business logic goes here

---

### 4. Complete Workflow Sequence Diagram
**Purpose**: Step-by-step execution flow from start to finish  
**Shows**:
- Initialization sequence
- Complete alert run cycle
- Method call order
- Data transformations
- Database interactions
- Email sending process
- Tracking updates

**Use this when**:
- Debugging execution flow
- Understanding when each method is called
- Tracing data through the system
- Identifying performance bottlenecks
- Understanding error handling points

**Read from top to bottom**: Time flows downward

---

### 5. Data Flow Diagram
**Purpose**: How data moves and transforms through the system  
**Shows**:
- 8 stages of data processing
- Input sources (SQL, .env, tracking file)
- Transformations at each stage
- Output destinations (emails, tracking file)

**Stages**:
1. Configuration loading
2. Database query execution
3. Data filtering and formatting
4. Tracking/deduplication
5. Routing to recipients
6. Email content formatting
7. Email sending
8. Tracking updates

**Use this when**:
- Understanding data transformations
- Adding new data processing steps
- Debugging data issues
- Optimizing data flow

---

### 6. Database Connection Flow
**Purpose**: SSH tunnel and database connection logic  
**Shows**:
- Decision tree for SSH vs direct connection
- Connection establishment
- Different query types (query_to_df, get_db_connection, check_db_connection)
- Resource cleanup
- Error handling

**Use this when**:
- Setting up SSH tunnel configuration
- Debugging connection issues
- Understanding connection modes
- Troubleshooting database access

**Key branches**:
- WITH SSH tunnel: localhost connection through tunnel
- WITHOUT SSH tunnel: direct connection to database

---

### 7. Tracking System State Machine
**Purpose**: Event tracking lifecycle and modes  
**Shows**:
- File initialization
- Two tracking modes (cleanup vs permanent)
- State transitions
- Data validation
- Atomic file operations

**Tracking modes**:
- **Cleanup mode**: reminder_frequency_days SET
  - Old events removed automatically
  - Allows re-sending after time passes
  - Tracking file stays bounded
  
- **Permanent mode**: reminder_frequency_days = None
  - All events tracked forever
  - Never re-sends same event
  - Tracking file grows indefinitely (recommended for Masters Nav Audit)

**Use this when**:
- Understanding tracking behavior
- Deciding on reminder frequency
- Debugging duplicate/missing notifications
- Understanding file corruption recovery

---

### 8. Email Routing Decision Tree
**Purpose**: How emails are routed to recipients  
**Shows**:
- Dry-run modes (block vs redirect)
- Production routing by domain
- CC recipient determination
- SMTP connection types
- Email composition process

**Routing logic**:
1. Check dry-run mode
2. Determine recipients based on domain
3. Add company-specific CC recipients
4. Add internal recipients (always)
5. Choose SMTP connection type
6. Send and track

**Use this when**:
- Understanding email routing logic
- Adding new company domains
- Debugging missing CC recipients
- Testing with dry-run modes

---

### 9. Scheduler Timing Modes
**Purpose**: Three scheduling modes and their behavior  
**Shows**:
- Time-based scheduling (specific times daily)
- Interval-based scheduling (every N hours)
- Run-once mode (manual execution)

**Scheduling modes**:
- **Time-based**: SCHEDULE_TIMES = "09:00,15:00,21:00"
  - Runs at specific times daily
  - Uses schedule_times_timezone
  - Calculates next run time
  
- **Interval-based**: SCHEDULE_FREQUENCY_HOURS = 1
  - Runs every N hours
  - Continuous loop with sleep
  - Runs immediately on startup
  
- **Run-once**: --run-once flag
  - Single execution
  - Exits after completion
  - Good for testing

**Use this when**:
- Configuring schedule timing
- Understanding when alerts run
- Debugging scheduler behavior
- Choosing between scheduling modes

---

### 10. Column Flow: From Database to Email
**Purpose**: Track individual columns through the system  
**Shows**:
- SQL query output columns
- Which columns appear in DataFrame
- How columns are used (tracking, display, routing)
- What appears in final email

**Column categories**:
- **Display columns**: Shown in email table
- **Tracking columns**: Used for deduplication
- **Routing columns**: Used for email routing
- **Metadata columns**: Used for subject/headers

**Use this when**:
- Understanding which columns are needed
- Adding new columns to SQL query
- Debugging missing data in emails
- Understanding column requirements

---

## Creating a New Alert Type

To create a new alert (e.g., "Hot Works Alert"), use these diagrams:

1. **Start with Diagram 3**: Alert-Specific Implementation
   - Copy MastersNavigationAuditAlert structure
   - Implement 6 abstract methods
   - Create new SQL query

2. **Reference Diagram 2**: Core Infrastructure
   - Understand what BaseAlert provides
   - See what methods you can call
   - Understand config object structure

3. **Use Diagram 4**: Workflow Sequence
   - See when each method is called
   - Understand execution order
   - Plan your implementation

4. **Check Diagram 5**: Data Flow
   - Understand data transformations
   - Plan your filtering logic
   - Decide what to display

5. **Consult Diagram 8**: Email Routing
   - Plan recipient logic
   - Decide on CC recipients
   - Plan domain routing

## Modifying Core Infrastructure

To modify reusable components:

1. **Review Diagram 1**: System Architecture
   - Understand impact on all alerts
   - Identify dependencies

2. **Study Diagram 2**: Class Diagram
   - See all methods and properties
   - Understand relationships
   - Plan backward compatibility

3. **Check Diagram 4**: Sequence Diagram
   - Understand method call order
   - Identify integration points

## Troubleshooting Guide

### Connection Issues
→ Use **Diagram 6**: Database Connection Flow

### Missing Notifications
→ Use **Diagram 7**: Tracking State Machine

### Wrong Recipients
→ Use **Diagram 8**: Email Routing Decision Tree

### Timing Issues
→ Use **Diagram 9**: Scheduler Timing Modes

### Data Problems
→ Use **Diagram 5**: Data Flow Diagram

### Missing Columns
→ Use **Diagram 10**: Column Flow

## Quick Reference

### Reusable Components (Copy Unchanged)
- AlertConfig (Diagram 2)
- AlertScheduler (Diagram 2, 9)
- EventTracker (Diagram 2, 7)
- BaseAlert (Diagram 2, 3)
- EmailSender (Diagram 2, 8)
- HTMLFormatter (Diagram 2)
- TextFormatter (Diagram 2)
- db_utils (Diagram 6)

### Alert-Specific Components (Customize Per Alert)
- Alert class implementation (Diagram 3)
- SQL query file (Diagram 3, 10)
- .env parameters (Diagram 1, 5)

### Data Files
- sent_alerts.json (Diagram 7)
- alerts.log (Diagram 1)
- health_status.txt (Diagram 1)

## Tips for Using These Diagrams

1. **Print key diagrams**: Keep Diagrams 1, 2, 4 on hand
2. **Reference during code review**: Check against sequence diagram
3. **Update when modifying**: Keep diagrams in sync with code
4. **Use in documentation**: Reference diagram numbers in code comments
5. **Share with team**: Include in onboarding materials

## Diagram Maintenance

When code changes:

1. Identify affected diagram(s) from the index
2. Update the relevant mermaid code
3. Test rendering in your preferred viewer
4. Commit changes with descriptive message

Example:
```bash
git add masters_navigation_audit_diagrams.md
git commit -m "docs: Update Diagram 3 to reflect new URL handling in MastersNavigationAuditAlert"
```

---

**Last Updated**: December 2025  
**Diagrams Version**: 1.0  
**Compatible with**: masters_navigation_audit v1.0
