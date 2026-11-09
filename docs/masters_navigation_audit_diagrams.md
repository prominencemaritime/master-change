# Master's Navigation Audit Alert System - Mermaid Diagrams

## 1. High-Level System Architecture

```mermaid
graph TB
    subgraph "Entry Point"
        Main[main.py]
    end
    
    subgraph "Core Infrastructure (Reusable)"
        Config[AlertConfig]
        Scheduler[AlertScheduler]
        Tracker[EventTracker]
        BaseAlert[BaseAlert<br/>Abstract Class]
    end
    
    subgraph "Notification Layer (Reusable)"
        EmailSender[EmailSender]
        HTMLFormatter[HTMLFormatter]
        TextFormatter[TextFormatter]
    end
    
    subgraph "Alert Implementation (Alert-Specific)"
        MastersAlert[MastersNavigationAuditAlert]
        SQLQuery[MastersNavigationAudit.sql]
    end
    
    subgraph "Database Layer (Reusable)"
        DBUtils[db_utils.py]
        PostgreSQL[(PostgreSQL<br/>Database)]
        SSH[SSH Tunnel<br/>Optional]
    end
    
    subgraph "Data Storage"
        TrackingFile[sent_alerts.json]
        LogFile[alerts.log]
        HealthFile[health_status.txt]
    end
    
    Main -->|1. Load config| Config
    Main -->|2. Setup logging| LogFile
    Main -->|3. Initialize| Tracker
    Main -->|4. Initialize| EmailSender
    Main -->|5. Initialize| HTMLFormatter
    Main -->|6. Initialize| TextFormatter
    Main -->|7. Create| Scheduler
    Main -->|8. Register alert| MastersAlert
    Main -->|9. Run| Scheduler
    
    Scheduler -->|triggers| MastersAlert
    MastersAlert -.->|inherits from| BaseAlert
    MastersAlert -->|uses| Config
    MastersAlert -->|queries via| DBUtils
    MastersAlert -->|loads| SQLQuery
    MastersAlert -->|filters via| Tracker
    MastersAlert -->|sends via| EmailSender
    
    BaseAlert -->|formats with| HTMLFormatter
    BaseAlert -->|formats with| TextFormatter
    BaseAlert -->|tracks with| Tracker
    BaseAlert -->|writes| HealthFile
    
    EmailSender -->|uses| HTMLFormatter
    EmailSender -->|uses| TextFormatter
    
    DBUtils -->|optional| SSH
    DBUtils -->|connects to| PostgreSQL
    
    Tracker -->|reads/writes| TrackingFile
    
    Config -.->|injected into| BaseAlert
    Config -.->|injected into| EmailSender
    Config -.->|injected into| Tracker
    
    style Main fill:#e1f5ff
    style Config fill:#fff4e1
    style Scheduler fill:#fff4e1
    style Tracker fill:#fff4e1
    style BaseAlert fill:#fff4e1
    style EmailSender fill:#e8f5e9
    style HTMLFormatter fill:#e8f5e9
    style TextFormatter fill:#e8f5e9
    style MastersAlert fill:#ffe1e1
    style SQLQuery fill:#ffe1e1
    style DBUtils fill:#fff4e1
```

## 2. Core Infrastructure Class Diagram (Reusable Components)

Shows the foundational base classes that all alert projects inherit from: BaseAlert orchestrates the workflow, EventTracker manages deduplication, and EmailSender handles notifications.

```mermaid
classDiagram
    class BaseAlert {
        +Config config
        +EventTracker tracker
        +EmailSender email_sender
        +Logger logger
        +run() bool
        #fetch_data() DataFrame
        #validate_required_columns(df)
        #filter_data(df) DataFrame
        #route_notifications(df) List
        #_send_notifications(jobs) bool
        #_write_health_status(status, time, error)
    }
    
    class EventTracker {
        +Path tracking_file
        +Dict tracked_events
        +int reminder_frequency_days
        +load_tracked_events()
        +filter_unsent_events(df) DataFrame
        +mark_as_sent(event_keys)
        +cleanup_old_events()
    }
    
    class EmailSender {
        +str smtp_host
        +int smtp_port
        +str smtp_user
        +str smtp_pass
        +send_email(to, subject, body) bool
        +send_teams_message(webhook, message) bool
    }
    
    class Config {
        +str db_host
        +str db_name
        +str timezone
        +str schedule_times
        +float schedule_frequency
        +validate()
    }
    
    BaseAlert --> EventTracker : uses
    BaseAlert --> EmailSender : uses
    BaseAlert --> Config : uses
    
    note for BaseAlert "Abstract base class\nDefines workflow template\nSubclasses implement specifics"
    note for EventTracker "Prevents duplicate alerts\nTracks sent notifications\nOptional reminder system"
    note for EmailSender "Handles SMTP and Teams\nRetry logic built-in\nSupports port 587 and 465"
```

## 3. Alert-Specific Implementation (Masters Navigation Audit)

Concrete implementation example: MastersNavigationAuditAlert extends BaseAlert and implements the four required methods (fetch, validate, filter, route) with domain-specific logic.

```mermaid
classDiagram
    class BaseAlert {
        +run() bool
        +fetch_data() DataFrame
        +validate_required_columns(df)
        +filter_data(df) DataFrame
        +route_notifications(df) List
    }
    
    class MastersNavigationAuditAlert {
        +fetch_data() DataFrame
        +validate_required_columns(df)
        +filter_data(df) DataFrame
        +route_notifications(df) List
        -format_email_body(row) str
        -create_teams_card(row) dict
    }
    
    class PostgresConnector {
        +connect() connection
        +execute_query(sql) DataFrame
        +close()
    }
    
    class EmailFormatter {
        +format_subject(row) str
        +format_body(row) str
        +add_vessel_info(body, row) str
    }
    
    class TeamsFormatter {
        +create_adaptive_card(row) dict
        +add_facts(card, data)
        +add_actions(card, links)
    }
    
    BaseAlert <|-- MastersNavigationAuditAlert
    MastersNavigationAuditAlert --> PostgresConnector
    MastersNavigationAuditAlert --> EmailFormatter
    MastersNavigationAuditAlert --> TeamsFormatter
```

## 4. Complete Workflow Sequence Diagram

```mermaid
sequenceDiagram
    participant Main as main.py
    participant Config as AlertConfig
    participant Scheduler as AlertScheduler
    participant Alert as MastersNavigationAuditAlert
    participant Base as BaseAlert
    participant DB as db_utils
    participant Tracker as EventTracker
    participant Email as EmailSender
    participant HTML as HTMLFormatter
    participant File as sent_alerts.json
    
    Main->>Config: from_env()
    Config-->>Main: config instance
    
    Main->>Config: validate()
    
    Main->>Config: initialize_components()
    Config->>Tracker: EventTracker(tracking_file, reminder_days, tz)
    Config->>Email: EmailSender(smtp_host, smtp_port, ...)
    Config->>HTML: HTMLFormatter()
    Config-->>Main: config (with runtime objects)
    
    Main->>Scheduler: AlertScheduler(frequency, timezone, schedule_times)
    Main->>Alert: MastersNavigationAuditAlert(config)
    Main->>Scheduler: register_alert(alert.run)
    Main->>Scheduler: run_continuous() / run_at_times()
    
    loop Every Schedule Interval
        Scheduler->>Alert: run()
        Alert->>Base: run() (inherited)
        
        Base->>Alert: fetch_data()
        Alert->>DB: validate_query_file(query_path)
        DB-->>Alert: SQL query string
        Alert->>DB: get_db_connection()
        Alert->>DB: pd.read_sql_query(query, conn, params)
        DB-->>Alert: DataFrame (all records)
        Alert-->>Base: DataFrame
        
        Base->>Base: validate_required_columns(df)
        
        Base->>Alert: filter_data(df)
        Alert->>Alert: Convert timezone, format dates
        Alert-->>Base: Filtered DataFrame
        
        Base->>Tracker: filter_unsent_events(df, key_func)
        Tracker->>File: Load sent_events from JSON
        Tracker->>Tracker: Filter out already-sent events
        Tracker-->>Base: Unsent DataFrame
        
        alt No unsent records
            Base-->>Scheduler: False (no notifications sent)
        else Has unsent records
            Base->>Alert: route_notifications(df_unsent)
            Alert->>Alert: Group by vessel
            Alert->>Alert: Determine CC recipients
            Alert->>Alert: Add URL links (if enabled)
            Alert-->>Base: List[notification_jobs]
            
            Base->>Base: _send_notifications(jobs, run_time)
            
            loop For each notification job
                Base->>Alert: get_subject_line(data, metadata)
                Alert-->>Base: Subject string
                
                Base->>HTML: format(data, run_time, config, metadata)
                HTML-->>Base: HTML content
                
                Base->>Email: send(subject, plain_text, html, recipients, cc)
                Email->>Email: Create MIME message
                Email->>Email: Attach logos
                Email->>Email: Connect SMTP
                Email-->>Base: (email sent)
                
                Base->>Alert: get_tracking_key(row) for each row
                Alert-->>Base: Tracking keys
            end
            
            Base->>Tracker: mark_as_sent(event_keys, run_time)
            Tracker->>File: Save updated sent_events to JSON
            
            Base-->>Scheduler: True (notifications sent)
        end
        
        Base->>Base: _write_health_status("OK", run_time)
    end
```

## 5. Data Flow Diagram

```mermaid
graph LR
    subgraph "1. Configuration"
        ENV[.env file]
        ENV --> CONFIG[AlertConfig.from_env]
    end
    
    subgraph "2. Database Query"
        SQL[MastersNavigationAudit.sql]
        SQL --> FETCH[fetch_data]
        FETCH --> DB[(PostgreSQL)]
        DB --> RAW[Raw DataFrame<br/>All Masters]
    end
    
    subgraph "3. Filtering"
        RAW --> FILTER[filter_data]
        FILTER --> TZ[Timezone Conversion]
        TZ --> DATE[Date Formatting]
        DATE --> FILTERED[Filtered DataFrame<br/>Recent Sign-ons]
    end
    
    subgraph "4. Tracking"
        FILTERED --> TRACK[filter_unsent_events]
        TRACKING[(sent_alerts.json)] --> TRACK
        TRACK --> UNSENT[Unsent DataFrame<br/>New Events Only]
    end
    
    subgraph "5. Routing"
        UNSENT --> ROUTE[route_notifications]
        ROUTE --> GROUP[Group by Vessel]
        GROUP --> CC[Add CC Recipients]
        CC --> LINKS[Add URL Links]
        LINKS --> JOBS[Notification Jobs<br/>List of Dicts]
    end
    
    subgraph "6. Formatting"
        JOBS --> SUBJECT[get_subject_line]
        JOBS --> HTML[HTMLFormatter.format]
        JOBS --> TEXT[TextFormatter.format]
        
        SUBJECT --> EMAIL_COMP[Email Components]
        HTML --> EMAIL_COMP
        TEXT --> EMAIL_COMP
    end
    
    subgraph "7. Sending"
        EMAIL_COMP --> SEND[EmailSender.send]
        LOGOS[media/*.png] --> SEND
        SEND --> SMTP[SMTP Server]
        SMTP --> RECIPIENTS[Email Recipients]
    end
    
    subgraph "8. Update Tracking"
        SEND --> UPDATE[mark_as_sent]
        UPDATE --> TRACKING
    end
    
    style CONFIG fill:#fff4e1
    style FETCH fill:#ffe1e1
    style FILTER fill:#ffe1e1
    style TRACK fill:#fff4e1
    style ROUTE fill:#ffe1e1
    style HTML fill:#e8f5e9
    style SEND fill:#e8f5e9
    style UPDATE fill:#fff4e1
```

## 6. Database Connection Flow

```mermaid
graph TB
    subgraph "db_utils Module"
        START[Function Called]
        
        START --> CHECK_SSH{USE_SSH_TUNNEL<br/>enabled?}
        
        CHECK_SSH -->|Yes| VERIFY_KEY{SSH Key<br/>exists?}
        VERIFY_KEY -->|No| ERROR1[Raise FileNotFoundError]
        VERIFY_KEY -->|Yes| CREATE_TUNNEL[Create SSHTunnelForwarder]
        
        CREATE_TUNNEL --> TUNNEL_UP[Tunnel Established]
        TUNNEL_UP --> LOCAL_CONN[Connect to localhost:tunnel_port]
        
        CHECK_SSH -->|No| DIRECT_CONN[Connect directly to DB_HOST:DB_PORT]
        
        LOCAL_CONN --> ENGINE[Create SQLAlchemy Engine]
        DIRECT_CONN --> ENGINE
        
        ENGINE --> EXECUTE{Function Type}
        
        EXECUTE -->|query_to_df| PANDAS[pd.read_sql]
        EXECUTE -->|get_db_connection| CONTEXT[Return Connection<br/>Context Manager]
        EXECUTE -->|check_db_connection| TEST[Execute SELECT 1]
        
        PANDAS --> RESULT1[Return DataFrame]
        CONTEXT --> RESULT2[Yield Connection]
        TEST --> RESULT3[Return bool]
        
        RESULT1 --> CLEANUP[Close Connection]
        RESULT2 --> CLEANUP
        RESULT3 --> CLEANUP
        
        CLEANUP --> CLOSE_TUNNEL{SSH Tunnel?}
        CLOSE_TUNNEL -->|Yes| TUNNEL_DOWN[Close SSH Tunnel]
        CLOSE_TUNNEL -->|No| END[Complete]
        TUNNEL_DOWN --> END
    end
    
    subgraph "External Systems"
        SSH_SERVER[SSH Server<br/>ssh.host.com]
        POSTGRES[(PostgreSQL<br/>db.host.com)]
    end
    
    CREATE_TUNNEL -.->|SSH Connection| SSH_SERVER
    SSH_SERVER -.->|Port Forward| POSTGRES
    LOCAL_CONN -.->|Through Tunnel| POSTGRES
    DIRECT_CONN -.->|Direct Connection| POSTGRES
    
    style START fill:#e1f5ff
    style ENGINE fill:#fff4e1
    style PANDAS fill:#e8f5e9
    style CONTEXT fill:#e8f5e9
    style TEST fill:#e8f5e9
    style ERROR1 fill:#ffebee
```

## 7. Tracking System State Machine

```mermaid
stateDiagram-v2
    [*] --> FileNotExists: Initialization
    [*] --> FileExists: Initialization
    
    FileNotExists --> EmptyState: Create fresh tracking
    FileExists --> LoadData: Read JSON file
    
    LoadData --> ValidateFormat: Parse JSON
    
    ValidateFormat --> EmptyState: Corrupted/Invalid
    ValidateFormat --> CheckReminder: Valid format
    
    CheckReminder --> CleanupMode: reminder_frequency_days SET
    CheckReminder --> PermanentMode: reminder_frequency_days = None
    
    CleanupMode --> FilterOld: Calculate cutoff date
    FilterOld --> SaveCleaned: Remove old events
    SaveCleaned --> ReadyState: Tracking loaded
    
    PermanentMode --> ReadyState: All events retained
    
    EmptyState --> ReadyState: Empty dict ready
    
    ReadyState --> FilterUnsent: Alert checks events
    FilterUnsent --> NewEvents: filter_unsent_events()
    
    NewEvents --> SendNotifications: Has unsent events
    NewEvents --> ReadyState: All already sent
    
    SendNotifications --> MarkSent: mark_as_sent()
    MarkSent --> AtomicWrite: Create temp file
    AtomicWrite --> ReplaceFile: Atomic rename
    ReplaceFile --> ReadyState: Tracking updated
    
    ReadyState --> [*]: System shutdown
    
    note right of CleanupMode
        Reminder mode:
        - Events older than N days removed
        - Allows re-sending after time passes
        - Tracking file stays bounded
    end note
    
    note right of PermanentMode
        Forever mode:
        - All events tracked permanently
        - Never re-sends same event
        - Tracking file grows indefinitely
    end note
```

## 8. Email Routing Decision Tree

Decision flow for determining email recipients: checks for vessel-specific contacts, falls back to default recipients, and applies BCC rules for record-keeping.

```mermaid
flowchart TD
    Start([Route Notification]) --> HasVessel{Row has<br/>vessel_email?}
    
    HasVessel -->|Yes| ValidEmail{Email valid<br/>and not empty?}
    HasVessel -->|No| UseDefault[Use default recipients<br/>from config]
    
    ValidEmail -->|Yes| VesselRecipient[Add vessel_email<br/>to TO field]
    ValidEmail -->|No| UseDefault
    
    VesselRecipient --> CheckCC{Config has<br/>CC_EMAILS?}
    UseDefault --> CheckCC
    
    CheckCC -->|Yes| AddCC[Add CC recipients]
    CheckCC -->|No| CheckBCC
    
    AddCC --> CheckBCC{Config has<br/>BCC_EMAILS?}
    
    CheckBCC -->|Yes| AddBCC[Add BCC recipients<br/>for record keeping]
    CheckBCC -->|No| CheckTeams
    
    AddBCC --> CheckTeams{Teams webhook<br/>configured?}
    
    CheckTeams -->|Yes| AddTeams[Add Teams notification<br/>to job]
    CheckTeams -->|No| CreateJob
    
    AddTeams --> CreateJob[Create notification job<br/>with all recipients]
    
    CreateJob --> End([Return job])
    
    style VesselRecipient fill:#90EE90
    style UseDefault fill:#FFE4B5
    style AddCC fill:#E1F5FF
    style AddBCC fill:#E1F5FF
    style AddTeams fill:#E1F5FF
    style CreateJob fill:#90EE90
```

## 9. Scheduler Timing Modes

```mermaid
graph TD
    INIT[Scheduler Initialization] --> MODE_CHECK{schedule_times<br/>configured?}
    
    MODE_CHECK -->|Yes| TIME_BASED[Time-Based Scheduling]
    MODE_CHECK -->|No| INTERVAL_BASED[Interval-Based Scheduling]
    
    subgraph "Time-Based Mode"
        TIME_BASED --> PARSE_TIMES[Parse schedule_times<br/>HH:MM format]
        PARSE_TIMES --> VALIDATE_TIMES[Validate time format]
        VALIDATE_TIMES --> CURRENT_TIME[Get current time<br/>in schedule_times_timezone]
        CURRENT_TIME --> FIND_NEXT{Any time<br/>remaining today?}
        
        FIND_NEXT -->|Yes| NEXT_TODAY[Next run = Today at HH:MM]
        FIND_NEXT -->|No| NEXT_TOMORROW[Next run = Tomorrow at earliest HH:MM]
        
        NEXT_TODAY --> CALC_SLEEP_TIME
        NEXT_TOMORROW --> CALC_SLEEP_TIME[Calculate sleep seconds]
        
        CALC_SLEEP_TIME --> SLEEP_TIME[Sleep until next_run]
        SLEEP_TIME --> RUN_ALERTS_TIME[Execute all alerts]
        RUN_ALERTS_TIME --> CURRENT_TIME
    end
    
    subgraph "Interval-Based Mode"
        INTERVAL_BASED --> RUN_NOW[Execute alerts immediately]
        RUN_NOW --> CALC_INTERVAL[Calculate sleep duration<br/>frequency_hours * 3600]
        CALC_INTERVAL --> SLEEP_INTERVAL[Sleep for calculated seconds]
        SLEEP_INTERVAL --> RUN_ALERTS_INTERVAL[Execute all alerts]
        RUN_ALERTS_INTERVAL --> CALC_INTERVAL
    end
    
    subgraph "Run-Once Mode"
        RUN_ONCE[run_once flag] --> SINGLE_RUN[Execute all alerts]
        SINGLE_RUN --> EXIT[Exit program]
    end
    
    INIT -.->|--run-once flag| RUN_ONCE
    
    style TIME_BASED fill:#e1f5ff
    style INTERVAL_BASED fill:#fff4e1
    style RUN_ONCE fill:#e8f5e9
```

## 10. Column Flow: From Database to Email

```mermaid
graph LR
    subgraph "SQL Query Output"
        SQL[MastersNavigationAudit.sql] --> COL1[crew_contract_id]
        SQL --> COL2[crew_member_id]
        SQL --> COL3[vessel_id]
        SQL --> COL4[vsl_email]
        SQL --> COL5[vessel]
        SQL --> COL6[surname]
        SQL --> COL7[full_name]
        SQL --> COL8[rank]
        SQL --> COL9[sign_on_date]
        SQL --> COL10[due_date]
    end
    
    subgraph "fetch_data Returns"
        COL1 --> DF[DataFrame with<br/>ALL columns]
        COL2 --> DF
        COL3 --> DF
        COL4 --> DF
        COL5 --> DF
        COL6 --> DF
        COL7 --> DF
        COL8 --> DF
        COL9 --> DF
        COL10 --> DF
    end
    
    subgraph "filter_data Processing"
        DF --> FILTER[filter_data]
        FILTER --> TZ[Timezone conversion<br/>on sign_on_date]
        TZ --> FORMAT[Format dates<br/>for display]
        FORMAT --> FILTERED[Filtered DataFrame<br/>SAME columns]
    end
    
    subgraph "route_notifications"
        FILTERED --> ROUTE[route_notifications]
        ROUTE --> GROUP[Group by vessel]
        GROUP --> ADD_URL[Add 'url' column<br/>if ENABLE_LINKS]
        ADD_URL --> META[Create metadata dict]
        
        META --> DISPLAY_LIST[display_columns =<br/>full_name, rank,<br/>sign_on_date, due_date]
    end
    
    subgraph "Email Content"
        DISPLAY_LIST --> GREETING[Captain surname<br/>for greeting]
        DISPLAY_LIST --> TABLE[HTML/Text Table<br/>with 4 columns]
        
        COL1 -.->|tracking only| TRACK[get_tracking_key]
        COL2 -.->|tracking only| TRACK
        COL3 -.->|metadata only| META
        COL4 -.->|routing only| META
        COL5 -.->|subject & metadata| META
        COL6 --> GREETING
        COL7 --> TABLE
        COL8 --> TABLE
        COL9 --> TABLE
        COL10 --> TABLE
    end
    
    style SQL fill:#ffe1e1
    style DF fill:#fff4e1
    style FILTERED fill:#fff4e1
    style DISPLAY_LIST fill:#e1f5ff
    style TABLE fill:#e8f5e9
```

## Legend

- **Yellow boxes** (🟨): Core infrastructure (reusable)
- **Green boxes** (🟩): Notification/formatting layer (reusable)  
- **Red boxes** (🟥): Alert-specific implementation
- **Blue boxes** (🟦): Entry points and configuration
