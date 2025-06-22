
import React, { useState, useEffect, useRef } from 'react';
import { createRoot } from 'react-dom/client';
import ZWTemplateVisualizer from './ZWTemplateVisualizer';
import ZWSyntaxHighlighter from './ZWSyntaxHighlighter'; // Import the new highlighter
import AutoCompleteDropdown from './AutoCompleteDropdown'; // Import AutoCompleteDropdown
import CopyButton from './CopyButton'; // Import the new CopyButton
import { GoogleGenAI, GenerateContentResponse } from "@google/genai";
import { ZWNode, ZWListItem, parseZW } from './zwParser';
import { convertZwToGodot } from './zwToGodotScript'; // Import Godot converter
import { convertJsonToZwString } from './jsonToZw'; // Import JSON to ZW converter
import { convertZwToJsonObject } from './zwToJson'; // Import ZW to JSON converter

// --- App Component ---
type TabKey = 'projects' | 'create' | 'validate' | 'visualize' | 'export' | 'library' | 'guide';

interface ZWSchemaComment {
  id: string;
  text: string;
  timestamp: string;
}

interface ZWSchemaDefinition {
  id: string;
  name: string;
  definition: string;
  comments?: ZWSchemaComment[];
  nlOrigin?: string; // Added field for Natural Language Origin
}

interface Project {
  id: string;
  name: string;
  description: string;
  schemas: ZWSchemaDefinition[];
}

interface ValidationFeedback {
  type: 'success' | 'error' | 'info' | 'warning';
  message: string;
  details?: string[];
  suggestions?: string[];
}

// --- Asset Source Status ---
interface AssetServiceStatusDetail {
  enabled: boolean;
  message: string;
  [key: string]: any; 
}

interface EngineRouterStatusDisplay { // To display router info from asset_source_statuses or /engines
    enabled: boolean;
    message: string;
    registered_engines?: number;
    default_engine?: string;
    engines?: Record<string, EngineDetail>; // This allows multi_engine_router to contain detailed engine info
}

interface AssetSourceStatus {
  services?: Record<string, AssetServiceStatusDetail>; 
  multi_engine_router?: EngineRouterStatusDisplay; // Specifically for the router from asset_source_statuses
  error?: string;      
  lastFetched?: string; 
  timestamp?: string; // Overall timestamp from the asset_source_statuses response
  // Allow direct top-level services for backward compatibility if daemon returns flat structure (handled in fetch)
  polyhaven?: AssetServiceStatusDetail;
  sketchfab?: AssetServiceStatusDetail;
  internalLibrary?: AssetServiceStatusDetail;
}


// --- Engine Info Interfaces (for /engines endpoint) ---
interface EngineDetail {
    name: string;
    version: string;
    capabilities: string[];
    status: string; // e.g., "active"
    [key: string]: any; // For other properties
}

// Updated EnginesInfo to hold fetched data, error, and status
interface EnginesInfo {
    router_status?: {
        registered_engines: number;
        default_engine: string | null;
        engines: Record<string, EngineDetail>; // Dictionary of engines by name
        total_capabilities: number;
    };
    capabilities?: Record<string, string[]>; // Capabilities per engine name
    timestamp?: string; // from the response
    error?: string;     // for fetch errors
    lastFetched?: string; // for state management
}


let ai: GoogleGenAI | null = null;
try {
    if (!process.env.API_KEY) {
        console.warn("API_KEY environment variable not set. Gemini API features will be disabled.");
        // alert("Gemini API_KEY not set. Natural Language features will be unavailable.");
    } else {
        // Corrected Gemini API initialization
        ai = new GoogleGenAI({ apiKey: process.env.API_KEY });
    }
} catch (error) {
    console.error("Failed to initialize GoogleGenAI:", error);
    // alert("Failed to initialize Gemini API. Natural Language features may be affected.");
}

const LOCAL_STORAGE_PROJECTS_KEY = 'zwTransformerProjects';
const LOCAL_STORAGE_ACTIVE_PROJECT_ID_KEY = 'zwTransformerActiveProjectId';
const LOCAL_STORAGE_BLENDER_PATH_KEY = 'zwTransformerBlenderPath'; 
const MCP_DAEMON_BASE_URL = 'http://localhost:1111';
const MCP_PROCESS_ZW_ENDPOINT = `${MCP_DAEMON_BASE_URL}/process_zw`;
const MCP_ASSET_STATUS_ENDPOINT = `${MCP_DAEMON_BASE_URL}/asset_source_statuses`;
const MCP_ENGINES_ENDPOINT = `${MCP_DAEMON_BASE_URL}/engines`;


// Example Templates
const EXAMPLE_USER_PROFILE_NL = `Create a user profile for a user with ID 'user_123', display name 'Alex', email 'alex@example.com', and avatar 'https://example.com/avatars/alex.png'. Their status is 'Online', and they prefer a dark theme, notifications enabled, and language set to 'en_US'. Tag them as 'gamer', 'developer', and 'sci-fi_fan'.`;
const EXAMPLE_USER_PROFILE_ZW = `ZW-USER-PROFILE:
  USER_ID: "user_123"
  DISPLAY_NAME: "Alex"
  EMAIL: "alex@example.com"
  AVATAR_URL: "https://example.com/avatars/alex.png"
  STATUS: "Online"
  PREFERENCES:
    THEME: "dark"
    NOTIFICATIONS_ENABLED: true
    LANGUAGE: "en_US"
  TAGS:
    - "gamer"
    - "developer"
    - "sci-fi_fan"
# This template stores basic user profile information and preferences.
# It demonstrates simple key-value pairs, nested sections, and lists.`;

const EXAMPLE_NARRATIVE_EVENT_NL = `Draft a narrative event: Captain Eva Rostova is on the bridge of a derelict spaceship. The goal is to introduce a mysterious artifact and her reaction, leading to a new objective. The mood is eerie and expectant. She brushes dust off a console, it activates showing alien script and a holographic orb (this is an ANCHOR point 'ArtifactActivated' and a FOCUS beat). Eva says, 'What in the void...? Never seen anything like this.' (DIALOGUE_ID: 'Eva_ArtifactReaction_01', EMOTION_TAG: 'Startled'). This triggers a new objective (LINKED_QUEST: 'InvestigateAlienTech'). Include metadata like author, version, and scene reference.`;
const EXAMPLE_NARRATIVE_EVENT_ZW = `ZW-NARRATIVE-EVENT:
  SCENE_GOAL: "Introduce a mysterious artifact and a character's immediate reaction, leading to a new objective."
  EVENT_ID: "artifact_discovery_001"
  FOCUS: true # Marks this event as a critical narrative beat.

  SETTING:
    LOCATION: "Dusty Derelict Spaceship - Bridge"
    TIME_OF_DAY: "Ship Time: 14:32"
    MOOD: "Eerie, Silent, Expectant"

  CHARACTERS_INVOLVED:
    - NAME: "Captain Eva Rostova"
      ROLE: "Player Character / Explorer"
      CURRENT_EMOTION: "Cautious"

  SEQUENCE: 
    - TYPE: ACTION
      ACTOR: "Eva Rostova"
      ACTION: "Brushes dust off a dormant console."
      SFX_SUGGESTION: "soft_brushing_cloth_metal.ogg"
    - TYPE: EVENT
      DESCRIPTION: "The console flickers to life, displaying an unknown alien script and a holographic orb."
      ANCHOR: "ArtifactActivated" 
      VFX_SUGGESTION: "hologram_flicker_reveal.anim"
    - TYPE: DIALOGUE
      ACTOR: "Eva Rostova"
      DIALOGUE_ID: "Eva_ArtifactReaction_01"
      CONTENT: "What in the void...? Never seen anything like this."
      EMOTION_TAG: "Startled" 
      DELIVERY_NOTE: "Whispered, voice filled with awe and apprehension."
    - TYPE: OBJECTIVE_UPDATE
      LINKED_QUEST: "InvestigateAlienTech" 
      STATUS: "NEW"
      OBJECTIVE_TEXT: "Investigate the alien orb and decipher the script."

  META:
    AUTHOR: "ZW Transformer Example"
    VERSION: "1.0"
    SCENE_REFERENCE: "Chapter1_BridgeEncounter"
    TRIGGER_CONDITION: "Player enters Bridge after power restoration."
    TAGS: ["discovery", "mystery", "alien_tech", "first_contact_incipient"]
# This ZW-NARRATIVE-EVENT template demonstrates a structured approach to defining
# interactive story moments, suitable for game engines and AI narrative systems.
# It includes character actions, environmental details, dialogue, and metadata.`;

const EXAMPLE_SIMPLE_TASK_NL = `Define a critical task with ID 'task_456' titled 'Investigate Anomaly in Sector Gamma-7'. Description: Pilot the scout ship to Sector Gamma-7 and perform a full sensor sweep of the reported energy signature. Assign it to 'eva_rostova_crew_id' with status 'Assigned', due by 'Ship Time: Cycle 3, Day 18:00'. List sub-tasks like pre-flight check, plot course, scan, approach, detailed sweep, and report. Required resources are 'Scout Ship Nomad' and 'Full Sensor Suite'.`;
const EXAMPLE_SIMPLE_TASK_ZW = `ZW-SIMPLE-TASK:
  TASK_ID: "task_456"
  TITLE: "Investigate Anomaly in Sector Gamma-7"
  DESCRIPTION: "Pilot the scout ship to Sector Gamma-7 and perform a full sensor sweep of the reported energy signature."
  PRIORITY: "Critical"
  STATUS: "Assigned" 
  ASSIGNEE_ID: "eva_rostova_crew_id"
  DUE_DATE: "Ship Time: Cycle 3, Day 18:00"
  SUB_TASKS:
    - "Pre-flight check Scout Ship 'Nomad'"
    - "Plot course to Gamma-7"
    - "Perform initial long-range scan"
    - "Approach anomaly cautiously"
    - "Execute detailed sensor sweep protocol"
    - "Report findings to Command"
  RESOURCES_REQUIRED:
    - "Scout Ship 'Nomad'"
    - "Full Sensor Suite"
# This template outlines a simple task or mission, useful for tracking objectives
# or procedural content generation in a game or simulation.`;


const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<TabKey>('create');
  // Projects State
  const [projects, setProjects] = useState<Project[]>([]);
  const [activeProjectId, setActiveProjectId] = useState<string | null>(null);
  const [newProjectName, setNewProjectName] = useState('');
  const [newProjectDescription, setNewProjectDescription] = useState('');

  // Create Tab State
  const [templateName, setTemplateName] = useState('');
  const [templateDefinition, setTemplateDefinition] = useState('');
  const [templateIdToEdit, setTemplateIdToEdit] = useState<string | null>(null);
  const [schemaComments, setSchemaComments] = useState<ZWSchemaComment[]>([]);
  const [newCommentText, setNewCommentText] = useState('');
  const [currentSchemaNlOrigin, setCurrentSchemaNlOrigin] = useState<string | undefined>(undefined);


  const [nlScenario, setNlScenario] = useState('');
  const [generatedZWPacket, setGeneratedZWPacket] = useState('');
  const [refinementSuggestion, setRefinementSuggestion] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);
  const [isNarrativeFocusEnabled, setIsNarrativeFocusEnabled] = useState(true);
  const [isSendingToMcp, setIsSendingToMcp] = useState(false);
  const [mcpStatusMessage, setMcpStatusMessage] = useState('');
  const [blenderExecutablePath, setBlenderExecutablePath] = useState<string>('');


  // Validation Tab State
  const [zwToValidate, setZwToValidate] = useState('');
  const [validationFeedback, setValidationFeedback] = useState<ValidationFeedback[]>([]);

  // Visualize Tab State
  const [zwToVisualize, setZwToVisualize] = useState('');
  const [jsonToConvertInput, setJsonToConvertInput] = useState('');
  const [jsonRootZwTypeInput, setJsonRootZwTypeInput] = useState('ZW-FROM-JSON');
  const [visualizedZwAsJsonString, setVisualizedZwAsJsonString] = useState('');


  // Export Tab State
  const [exportFilename, setExportFilename] = useState('zw_export.txt');
  const [exportAllFilename, setExportAllFilename] = useState('project_schemas.txt');
  const [godotExportFilename, setGodotExportFilename] = useState('schema_export.gd');


  // Auto-completion state
  const [autoCompleteSuggestions, setAutoCompleteSuggestions] = useState<string[]>([]);
  const [showAutoComplete, setShowAutoComplete] = useState(false);
  const [activeSuggestionIndex, setActiveSuggestionIndex] = useState(0);
  const [autoCompletePosition, setAutoCompletePosition] = useState({ top: 0, left: 0 });
  const templateTextareaRef = useRef<HTMLTextAreaElement>(null);

  // Asset Source & Engine Status State
  const [assetSourceStatuses, setAssetSourceStatuses] = useState<AssetSourceStatus | null>(null);
  const [isFetchingAssetStatuses, setIsFetchingAssetStatuses] = useState<boolean>(false);
  const [engineInfo, setEngineInfo] = useState<EnginesInfo | null>(null);
  const [isFetchingEngineInfo, setIsFetchingEngineInfo] = useState<boolean>(false);


  const activeProject = projects.find(p => p.id === activeProjectId);

  // --- Utility Functions ---
  const generateId = () => `id_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;

  const downloadFile = (filename: string, content: string, contentType: string = 'text/plain') => {
    console.log('[DownloadFile] Attempting to download:', { filename, contentType, contentLength: content.length });
    if (!filename || filename.trim() === "") {
      console.error("[DownloadFile] Error: Filename is empty or invalid.");
      alert("Error: Download filename is invalid.");
      return;
    }
    if (content === undefined || content === null) {
      console.error("[DownloadFile] Error: Content for download is undefined or null.");
      alert("Error: No content to download.");
      return;
    }

    try {
      const element = document.createElement('a');
      const file = new Blob([content], { type: contentType });
      element.href = URL.createObjectURL(file);
      console.log('[DownloadFile] Blob URL created:', element.href);
      element.download = filename;
      document.body.appendChild(element);
      console.log('[DownloadFile] Link element appended to body.');
      element.click();
      console.log('[DownloadFile] Link element clicked programmatically.');
      document.body.removeChild(element);
      console.log('[DownloadFile] Link element removed from body.');
      URL.revokeObjectURL(element.href); 
      console.log('[DownloadFile] Blob URL revoked.');
    } catch (error) {
      console.error('[DownloadFile] Error during file download process:', error);
      alert(`An error occurred during download: ${error instanceof Error ? error.message : String(error)}`);
    }
  };


  // --- Project Management & Blender Path Loading ---
  useEffect(() => {
    const storedProjects = localStorage.getItem(LOCAL_STORAGE_PROJECTS_KEY);
    if (storedProjects) {
      setProjects(JSON.parse(storedProjects));
    }
    const storedActiveProjectId = localStorage.getItem(LOCAL_STORAGE_ACTIVE_PROJECT_ID_KEY);
    if (storedActiveProjectId) {
      setActiveProjectId(storedActiveProjectId);
    }
    const storedBlenderPath = localStorage.getItem(LOCAL_STORAGE_BLENDER_PATH_KEY);
    if (storedBlenderPath) {
      setBlenderExecutablePath(storedBlenderPath);
    }
  }, []);

  useEffect(() => {
    localStorage.setItem(LOCAL_STORAGE_PROJECTS_KEY, JSON.stringify(projects));
  }, [projects]);

  useEffect(() => {
    if (activeProjectId) {
      localStorage.setItem(LOCAL_STORAGE_ACTIVE_PROJECT_ID_KEY, activeProjectId);
    } else {
      localStorage.removeItem(LOCAL_STORAGE_ACTIVE_PROJECT_ID_KEY);
    }
  }, [activeProjectId]);

  useEffect(() => {
    localStorage.setItem(LOCAL_STORAGE_BLENDER_PATH_KEY, blenderExecutablePath);
  }, [blenderExecutablePath]);

  // Fetch statuses on mount
  useEffect(() => {
    fetchAssetSourceStatuses();
    fetchEngineInfo();
  }, []);


  const handleCreateProject = () => {
    if (!newProjectName.trim()) {
      alert('Project name cannot be empty.');
      return;
    }
    const newProject: Project = {
      id: generateId(),
      name: newProjectName,
      description: newProjectDescription,
      schemas: [],
    };
    setProjects(prev => [...prev, newProject]);
    setActiveProjectId(newProject.id);
    setNewProjectName('');
    setNewProjectDescription('');
  };

  const handleDeleteProject = (projectId: string) => {
    if (window.confirm("Are you sure you want to delete this project and all its schemas? This action cannot be undone.")) {
      setProjects(prev => prev.filter(p => p.id !== projectId));
      if (activeProjectId === projectId) {
        setActiveProjectId(null);
        handleNewTemplate();
      }
    }
  };

  const handleSetActiveProject = (projectId: string) => {
    setActiveProjectId(projectId);
    handleNewTemplate();
  };

  const handleLoadExampleTemplates = () => {
    const exampleProjectName = "Example ZW Templates";
    let exampleProject = projects.find(p => p.name === exampleProjectName);
    let projectExisted = !!exampleProject;

    const examples: { name: string; definition: string; nlOrigin: string; commentsText?: string }[] = [
        {
            name: "User Profile",
            definition: EXAMPLE_USER_PROFILE_ZW,
            nlOrigin: EXAMPLE_USER_PROFILE_NL,
            commentsText: "This template stores basic user profile information and preferences. It demonstrates simple key-value pairs, nested sections, and lists."
        },
        {
            name: "Narrative Event (Gold Standard)",
            definition: EXAMPLE_NARRATIVE_EVENT_ZW,
            nlOrigin: EXAMPLE_NARRATIVE_EVENT_NL,
            commentsText: "This ZW-NARRATIVE-EVENT template demonstrates a structured approach to defining interactive story moments, suitable for game engines and AI narrative systems. It includes character actions, environmental details, dialogue, and metadata."
        },
        {
            name: "Simple Task",
            definition: EXAMPLE_SIMPLE_TASK_ZW,
            nlOrigin: EXAMPLE_SIMPLE_TASK_NL,
            commentsText: "This template outlines a simple task or mission, useful for tracking objectives or procedural content generation in a game or simulation."
        }
    ];
    
    let currentExampleProjectId = exampleProject?.id;

    if (!projectExisted) {
        const newExampleProjectData: Project = {
            id: generateId(),
            name: exampleProjectName,
            description: "Pre-loaded example templates to demonstrate ZW usage.",
            schemas: [],
        };
        currentExampleProjectId = newExampleProjectData.id;
        setProjects(prev => [...prev, newExampleProjectData]); 
    }


    setProjects(prevProjects => {
        return prevProjects.map(p => {
            if (p.id === currentExampleProjectId || (projectExisted && p.name === exampleProjectName)) {
                const updatedSchemas = [...p.schemas];
                let schemasAddedCount = 0;
                examples.forEach(ex => {
                    if (!p.schemas.some(s => s.name === ex.name)) { 
                        const newSchema: ZWSchemaDefinition = {
                            id: generateId(),
                            name: ex.name,
                            definition: ex.definition,
                            nlOrigin: ex.nlOrigin,
                            comments: ex.commentsText ? [{ id: generateId(), text: ex.commentsText, timestamp: new Date().toISOString() }] : [],
                        };
                        updatedSchemas.push(newSchema);
                        schemasAddedCount++;
                    }
                });
                 if (schemasAddedCount > 0 || !projectExisted) { 
                    if (currentExampleProjectId) setActiveProjectId(currentExampleProjectId);
                    alert(`${exampleProjectName} ${!projectExisted ? 'created' : 'updated'} with ${schemasAddedCount} new template(s) and set as active project.`);
                 } else {
                    if (currentExampleProjectId) setActiveProjectId(currentExampleProjectId);
                    alert(`${exampleProjectName} is already up to date and set as active project.`);
                 }

                if (schemasAddedCount > 0 || !projectExisted) {
                    const firstExampleSchemaDetails = examples[0];
                    const schemaToLoad = updatedSchemas.find(s => s.name === firstExampleSchemaDetails.name);
                    if(schemaToLoad) handleLoadSchema(schemaToLoad);
                }
                return { ...p, schemas: updatedSchemas };
            }
            return p;
        });
    });
};


  // --- Template Management (Create Tab) ---
  const handleNewTemplate = () => {
    setTemplateName('');
    setTemplateDefinition('');
    setTemplateIdToEdit(null);
    setSchemaComments([]);
    setCurrentSchemaNlOrigin(undefined);
  };

  const handleSaveSchemaToProject = () => {
    if (!activeProject) {
      alert('Please select or create a project first.');
      return;
    }
    if (!templateName.trim()) {
      alert('Template name cannot be empty.');
      return;
    }
    if (!templateDefinition.trim()) {
      alert('Template definition cannot be empty.');
      return;
    }

    setProjects(prevProjects =>
      prevProjects.map(p => {
        if (p.id === activeProjectId) {
          let updatedSchemas;
          if (templateIdToEdit) { 
            updatedSchemas = p.schemas.map(s =>
              s.id === templateIdToEdit ? { ...s, name: templateName, definition: templateDefinition, comments: schemaComments, nlOrigin: currentSchemaNlOrigin } : s
            );
          } else { 
            const newSchema: ZWSchemaDefinition = {
              id: generateId(),
              name: templateName,
              definition: templateDefinition,
              comments: schemaComments,
              nlOrigin: currentSchemaNlOrigin 
            };
            updatedSchemas = [...p.schemas, newSchema];
            setTemplateIdToEdit(newSchema.id); 
          }
          return { ...p, schemas: updatedSchemas };
        }
        return p;
      })
    );
    alert(`Template "${templateName}" saved to project "${activeProject.name}".`);
  };

  const handleLoadSchema = (schema: ZWSchemaDefinition) => {
    setTemplateName(schema.name);
    setTemplateDefinition(schema.definition);
    setTemplateIdToEdit(schema.id);
    setSchemaComments(schema.comments || []);
    setCurrentSchemaNlOrigin(schema.nlOrigin);
    setActiveTab('create'); 
  };

  const handleDeleteSchema = (schemaId: string) => {
    if (!activeProject) return;
    if (window.confirm("Are you sure you want to delete this template?")) {
      setProjects(prevProjects =>
        prevProjects.map(p => {
          if (p.id === activeProjectId) {
            const updatedSchemas = p.schemas.filter(s => s.id !== schemaId);
            return { ...p, schemas: updatedSchemas };
          }
          return p;
        })
      );
      if (templateIdToEdit === schemaId) {
        handleNewTemplate(); 
      }
      alert("Template deleted.");
    }
  };

  const handleAddComment = () => {
    if (!newCommentText.trim()) return;
    const newComment: ZWSchemaComment = {
      id: generateId(),
      text: newCommentText,
      timestamp: new Date().toISOString()
    };
    setSchemaComments(prev => [...prev, newComment]);
    setNewCommentText('');
  };

  const handleDeleteComment = (commentId: string) => {
    setSchemaComments(prev => prev.filter(c => c.id !== commentId));
  };


  // --- Gemini API Interaction ---
  const getNarrativeFocusPrompt = (scenario: string, projectTemplates?: ZWSchemaDefinition[]) => {
    let prompt = `You are an expert in narrative design and game development, specializing in the ZW (Ziegelwagga) consciousness pattern language.
The user wants to generate a ZW packet for the following scenario:
"${scenario}"

Your primary goal is to structure this scenario into a ZW-NARRATIVE-SCENE packet. This format is designed for cinematic game scripting, AI story management, and emotional choreography.
Key elements to include in ZW-NARRATIVE-SCENE (if applicable based on the scenario):
1.  SCENE_GOAL: (Root) A concise summary of the scene's narrative purpose.
2.  EVENT_ID: (Root) A unique identifier for this event or scene.
3.  FOCUS: (Root or within SEQUENCE items) Boolean (true) to mark critical narrative or emotional beats.
4.  SETTING: Section for LOCATION, TIME_OF_DAY, MOOD.
5.  CHARACTERS_INVOLVED: List of characters with NAME, ROLE, CURRENT_EMOTION.
6.  SEQUENCE_PARTS: (Optional, for longer scenes) A list of parts, each with a LABEL (e.g., "ArrivalAndVillage") and EVENTS (a list of sequence items). If not using SEQUENCE_PARTS, use a single SEQUENCE list directly.
7.  SEQUENCE: A list of events, dialogues, actions in order. Each item should have a TYPE (e.g., DIALOGUE, ACTION, EVENT, OBSERVATION, EMOTIONAL_BEAT).
    *   For DIALOGUE: include ACTOR, DIALOGUE_ID (unique for branching/memory), CONTENT, EMOTION_TAG (use a consistent, controlled vocabulary like Startled, Determined, Joyful, Anxious, Ominous), DELIVERY_NOTE (optional).
    *   For ACTION: include ACTOR, ACTION (concise description, e.g., "Opens the creaky door"), TARGET (optional). Consider moving detailed narrative framing into a child META or comment.
    *   For EVENT: include DESCRIPTION, ANCHOR (optional, unique ID for timeline jumps, e.g., "AwakeningTrigger_CombatPhaseStart").
8.  OBJECTIVE_UPDATE: (Optional, can be a SEQUENCE item) To modify game objectives. Include LINKED_QUEST (ID for quest system), STATUS, OBJECTIVE_TEXT.
9.  META: (Root) A block for production metadata: AUTHOR, VERSION, SCENE_REFERENCE, TIMESTAMP (in-game or real), TRIGGER_CONDITION, TAGS (list of relevant themes or keywords like "discovery", "betrayal"), QUESTS_STARTED, QUESTS_COMPLETED, ANCHORS_SET.

Prioritize user-defined templates from their project if they seem more appropriate than the generic ZW-NARRATIVE-SCENE for the given scenario.
Here are the available project templates (use the ZW Type as the primary key, e.g., ZW-MY-CUSTOM-EVENT):
`;

    if (projectTemplates && projectTemplates.length > 0) {
      projectTemplates.forEach(schema => {
        prompt += `\nSchema Name: ${schema.name}\n${schema.definition}\n---\n`;
      });
      prompt += "\nIf one of these project templates is a better fit for the user's scenario, please use that ZW Type and structure instead of ZW-NARRATIVE-SCENE. Adapt the scenario to the chosen template's fields.\n";
    } else {
      prompt += "\nNo specific project templates provided. Use the ZW-NARRATIVE-SCENE structure as described above.\n";
    }

    prompt += `
Example of ZW-NARRATIVE-SCENE structure:
ZW-NARRATIVE-SCENE:
  SCENE_GOAL: "Introduce protagonists, trigger awakening, establish threat, pivot to escape and revelation arc."
  EVENT_ID: "CH1_SC01_Intro"
  FOCUS: true
  SETTING:
    LOCATION: "Old Observatory - Control Room"
    TIME_OF_DAY: "Night, Stormy"
    MOOD: "Suspenseful, Foreboding"
  CHARACTERS_INVOLVED:
    - NAME: "Keen"
      ROLE: "Protagonist, Scientist"
      CURRENT_EMOTION: "Anxious"
    - NAME: "Garic"
      ROLE: "Mentor, Lead Researcher"
      CURRENT_EMOTION: "Concerned"
  SEQUENCE_PARTS: 
    - LABEL: "Initial tremors and system failure"
      EVENTS:
        - TYPE: EVENT
          DESCRIPTION: "The ground trembles. Red emergency lights flash. Alarms blare."
          SFX_SUGGESTION: "rumble_deep.ogg, alarm_klaxon_loop.ogg"
        - TYPE: DIALOGUE
          ACTOR: "Keen"
          DIALOGUE_ID: "Keen_TremorReaction_001"
          CONTENT: "What was that? Main power is offline!"
          EMOTION_TAG: "Startled"
          FOCUS: true
        - TYPE: ACTION
          ACTOR: "Garic"
          ACTION: "Checks secondary console, grimaces."
          DESCRIPTION: "Frantically types on the auxiliary power console."
    - LABEL: "The Anomaly Appears"
      EVENTS:
        - TYPE: EVENT
          DESCRIPTION: "A blinding light erupts from the main telescope array. Consoles spark."
          ANCHOR: "AnomalyAppearance"
          VFX_SUGGESTION: "bright_flash_energy_surge.anim"
          FOCUS: true
        - TYPE: DIALOGUE
          ACTOR: "Garic"
          DIALOGUE_ID: "Garic_AnomalyWarning_001"
          LINKED_QUEST: "InvestigateTheAnomaly" 
          CONTENT: "It's... it's not stable! We need to get out of here, Keen!"
          EMOTION_TAG: "Frantic"
          DELIVERY_NOTE: "Shouted over the noise."
  META:
    AUTHOR: "Narrative AI Assistant"
    VERSION: "0.8"
    SCENE_REFERENCE: "Chapter1_ObservatoryAttack"
    TRIGGER_CONDITION: "Player completes tutorial"
    TAGS: ["anomaly", "escape", "tech_failure"]
    QUESTS_STARTED: ["InvestigateTheAnomaly"]
    ANCHORS_SET: ["AnomalyAppearance"]

Generate ONLY the ZW packet. Do not include any explanatory text before or after the ZW block.
The ZW packet should be well-formed and adhere to the ZW syntax (indented key-value pairs, lists with '-').
`;
    return prompt;
  };

  const handleGenerateZWFromNL = async () => {
    if (!ai) {
      alert("Gemini API not initialized. Please ensure API_KEY is set and valid, or check console for details.");
      return;
    }
    if (!nlScenario.trim()) {
      alert('Please enter a natural language scenario.');
      return;
    }
    setIsGenerating(true);
    setGeneratedZWPacket('');
    setValidationFeedback([]);
    setMcpStatusMessage(''); 

    let promptText = "";
    if (isNarrativeFocusEnabled) {
        promptText = getNarrativeFocusPrompt(nlScenario, activeProject?.schemas);
    } else {
        promptText = `You are an expert in the ZW (Ziegelwagga) consciousness pattern language.
Convert the following natural language scenario into a ZW packet.
If project-specific templates are provided below, prioritize using them if they fit the scenario.
The ZW packet should be well-formed (indented key-value pairs, lists with '-').
Generate ONLY the ZW packet.

Scenario: "${nlScenario}"
`;
        if (activeProject && activeProject.schemas.length > 0) {
            promptText += "\nAvailable Project Templates (use the ZW Type as the primary key):\n";
            activeProject.schemas.forEach(schema => {
                promptText += `\nSchema Name: ${schema.name}\n${schema.definition}\n---\n`;
            });
        } else {
            promptText += `\nNo specific project templates are available to guide the structure.
Therefore, you MUST generate a ZW packet that begins with a root type declaration on its own line.
Use a generic root type like 'ZW-INFERRED-DATA:'. All subsequent content must be indented under this root type.
For example, if the scenario implies a user with a name and an email, the output should look like:
ZW-INFERRED-DATA:
  USER_NAME: "Example User"
  EMAIL: "user@example.com"
Ensure the very first line of your response is the ZW root type (e.g., ZW-INFERRED-DATA:) followed by a newline, and then the indented content.
`;
        }
    }

    try {
      const result: GenerateContentResponse = await ai.models.generateContent({
        model: 'gemini-2.5-flash-preview-04-17', 
        contents: [{role: "user", parts: [{text: promptText}]}],
      });
      const text = result.text.trim();
      setGeneratedZWPacket(text);
      validateZwContent(text, 'Generated Packet Validation');
    } catch (error) {
      console.error('Error generating ZW from NL:', error);
      alert(`Error generating ZW: ${error instanceof Error ? error.message : String(error)}`);
      setGeneratedZWPacket(`# Error generating ZW: ${error instanceof Error ? error.message : String(error)}`);
    } finally {
      setIsGenerating(false);
    }
  };

  const handleRefineZWFromNL = async () => {
    if (!ai) {
      alert("Gemini API not initialized. Please ensure API_KEY is set and valid, or check console for details.");
      return;
    }
    if (!generatedZWPacket.trim()) {
      alert('No ZW packet to refine. Please generate one first.');
      return;
    }
    if (!refinementSuggestion.trim()) {
      alert('Please enter a refinement suggestion.');
      return;
    }
    setIsGenerating(true);
    setMcpStatusMessage(''); 

    const promptText = `You are an expert in the ZW (Ziegelwagga) consciousness pattern language.
The user has a ZW packet and wants to refine it based on their suggestion.
Original ZW Packet:
${generatedZWPacket}

User's Refinement Suggestion: "${refinementSuggestion}"

Please apply the suggestion and return the refined ZW packet.
If the suggestion is unclear or impossible to apply directly to ZW structure, explain why in comments within the ZW packet itself if possible, or try your best to interpret the user's intent.
Ensure the refined packet is well-formed.
Generate ONLY the refined ZW packet.
`;
    try {
      const result: GenerateContentResponse = await ai.models.generateContent({
        model: 'gemini-2.5-flash-preview-04-17',
        contents: [{role: "user", parts: [{text: promptText}]}],
      });
      const text = result.text.trim();
      setGeneratedZWPacket(text);
      setRefinementSuggestion(''); 
      validateZwContent(text, 'Refined Packet Validation');
    } catch (error) {
      console.error('Error refining ZW:', error);
      alert(`Error refining ZW: ${error instanceof Error ? error.message : String(error)}`);
      setGeneratedZWPacket(`# Error refining ZW: ${generatedZWPacket}\n# Refinement failed: ${error instanceof Error ? error.message : String(error)}`);
    } finally {
      setIsGenerating(false);
    }
  };

  // --- Send ZW to MCP Daemon ---
  const handleSendZwToMcp = async () => {
    if (!generatedZWPacket.trim()) {
      setMcpStatusMessage("❌ No ZW packet content to send.");
      return;
    }
    setIsSendingToMcp(true);
    setMcpStatusMessage("🔄 Sending ZW data to Multi-Engine Router...");

    let zwDataToSend = generatedZWPacket;
    // Strip markdown code fences
    const codeFenceRegex = /^```(?:[a-zA-Z0-9_-]+)?\s*\n?([\s\S]*?)\s*\n?```$/;
    const fenceMatch = zwDataToSend.match(codeFenceRegex);
    if (fenceMatch && fenceMatch[1]) {
        zwDataToSend = fenceMatch[1];
    }
    zwDataToSend = zwDataToSend.trim(); // Ensure it's trimmed after stripping

    const payload: { zw_data: string; route_to_blender?: boolean; blender_path?: string; target_engines?: string[] } = {
        zw_data: zwDataToSend,
    };

    if (blenderExecutablePath.trim()) {
        payload.blender_path = blenderExecutablePath.trim();
        payload.target_engines = ["blender"];
    } else {
        payload.target_engines = ["blender"]; // Default to Blender if no path specified (daemon will use its default)
    }

    try {
      const response = await fetch(MCP_PROCESS_ZW_ENDPOINT, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      });

      const responseData = await response.json().catch(() => ({ 
          error: "Failed to parse daemon JSON response", 
          statusText: response.statusText, 
          ok: response.ok, 
          status: response.status 
      }));

      if (!response.ok) {
        let errorDetail = responseData.error || responseData.detail || responseData.message || responseData.statusText || 'Unknown server error.';
        if (typeof responseData.results === 'object' && responseData.results !== null) {
            const engineErrors = Object.entries(responseData.results)
                .filter(([_, engResult]: [string, any]) => engResult?.status === 'error' && engResult?.message)
                .map(([engName, engResult]: [string, any]) => `${engName}: ${engResult.message}`)
                .join('; ');
            if (engineErrors) errorDetail += ` Engine errors: ${engineErrors}`;
        }
        throw new Error(`MCP daemon responded with ${response.status}: ${errorDetail}`);
      }
      
      let msg = ``;
      if (responseData.status === 'success' || responseData.status === 'partial_failure' || responseData.status === 'error') {
        msg += `✅ Daemon Overall Status: **${responseData.status.toUpperCase()}**\n`;
        msg += `Engines Used: ${responseData.engines_used?.join(', ') || 'N/A'}\n`;
        msg += `Successful Engines: ${responseData.successful_engines ?? 0}/${responseData.total_engines ?? 0}\n\n`;

        if (responseData.results) {
          for (const engineName in responseData.results) {
            const result = responseData.results[engineName];
            msg += `**Engine: ${engineName.charAt(0).toUpperCase() + engineName.slice(1)}**\n`;
            msg += `  Status: ${result?.status || 'N/A'}\n`;
            if (result?.message) msg += `  Message: ${result.message}\n`;
            if (result?.blender_results && Array.isArray(result.blender_results)) { 
                const createdCount = result.blender_results.filter((r: any) => r?.status === 'success').length;
                const totalAttempted = result.blender_results.length;
                msg += `  Blender Objects: ${createdCount}/${totalAttempted} created\n`;
            }
            if (result?.stdout) msg += `  Output (stdout):\n---\n${result.stdout.trim()}\n---\n`;
            if (result?.stderr) msg += `  Errors (stderr):\n---\n${result.stderr.trim()}\n---\n`;
            msg += "\n";
          }
        }
         if (responseData.parsed_sections) {
            msg += `**ZW Blocks Parsed by Daemon:** ${responseData.parsed_sections.join(', ')}\n`;
          }

      } else {
         msg = `ℹ️ Unexpected response structure from daemon: ${JSON.stringify(responseData, null, 2)}`;
      }
      setMcpStatusMessage(msg.trim());

    } catch (error) {
      console.error('[MCP Send] Error:', error);
      setMcpStatusMessage(`❌ Error communicating with MCP daemon: ${error instanceof Error ? error.message : String(error)}`);
    } finally {
      setIsSendingToMcp(false);
    }
  };


  // --- ZW Validation (Create & Validate Tabs) ---
  const validateZwContent = (content: string, contextLabel: string = "Current Content") => {
    if (!content.trim()) {
      setValidationFeedback([{ type: 'warning', message: `No ZW content provided for ${contextLabel} to validate.` }]);
      return false;
    }
    try {
      const parsedRoot = parseZW(content);
      if (parsedRoot && !parsedRoot.key.startsWith('Error:')) {
        setValidationFeedback([{ type: 'success', message: `✅ ${contextLabel} is valid ZW! Root Type: ${parsedRoot.key}` }]);
        return true;
      } else if (parsedRoot && parsedRoot.key.startsWith('Error:')) {
        setValidationFeedback([{ type: 'error', message: `❌ ${contextLabel} - ZW Parsing Error: ${parsedRoot.key}`, details: [typeof parsedRoot.value === 'string' ? parsedRoot.value : 'No further details.'] }]);
        return false;
      } else {
        setValidationFeedback([{ type: 'error', message: `❌ ${contextLabel} is invalid. Parser returned null.`}]);
        return false;
      }
    } catch (e) {
      setValidationFeedback([{ type: 'error', message: `❌ ${contextLabel} - Critical Parsing Error: ${e instanceof Error ? e.message : String(e)}`}]);
      return false;
    }
  };

  const handleValidateCurrentEditor = () => {
    validateZwContent(templateDefinition, "Template Editor");
    setActiveTab('validate');
  };

  const handleValidateZwToValidateField = () => {
    validateZwContent(zwToValidate, "Validation Input Field");
  };

  // --- ZW to JSON Conversion (Visualize Tab) ---
  const handleConvertZwToVisualizeJson = () => {
    if (!zwToVisualize.trim()) {
      setVisualizedZwAsJsonString('// Enter ZW in the field above to convert to JSON');
      return;
    }
    const jsonObj = convertZwToJsonObject(zwToVisualize);
    if (jsonObj) {
      setVisualizedZwAsJsonString(JSON.stringify(jsonObj, null, 2));
    } else {
      setVisualizedZwAsJsonString('// Error: Could not convert ZW to JSON. Check ZW syntax.');
    }
  };

  // --- JSON to ZW Conversion (Visualize Tab) ---
  const handleConvertJsonToZw = () => {
    if (!jsonToConvertInput.trim()) {
      setZwToVisualize('// Enter JSON in the field above to convert to ZW');
      return;
    }
    try {
      const zwString = convertJsonToZwString(jsonToConvertInput, jsonRootZwTypeInput || undefined);
      setZwToVisualize(zwString);
    } catch (e) {
      setZwToVisualize(`# Error converting JSON to ZW: ${e instanceof Error ? e.message : String(e)}`);
    }
  };

  // --- Export Functionality (Export Tab) ---
  const handleExportGeneratedPacket = (format: 'zw' | 'json' | 'godot') => {
    if (!generatedZWPacket.trim()) {
      alert("No generated ZW packet to export.");
      return;
    }
    let content = '';
    let effectiveFilename = exportFilename;
    let contentType = 'text/plain';

    try {
      if (format === 'json') {
        const jsonObj = convertZwToJsonObject(generatedZWPacket);
        if (!jsonObj) throw new Error("Failed to parse ZW into JSON object for export.");
        content = JSON.stringify(jsonObj, null, 2);
        effectiveFilename = exportFilename.replace(/\.[^/.]+$/, "") + ".json";
        contentType = 'application/json';
      } else if (format === 'godot') {
        const parsedRoot = parseZW(generatedZWPacket);
        if (!parsedRoot || parsedRoot.key.startsWith('Error:')) {
            throw new Error(`Invalid ZW for Godot export: ${parsedRoot?.key || 'Unknown error'} ${parsedRoot?.value || ''}`);
        }
        content = convertZwToGodot(parsedRoot);
        effectiveFilename = godotExportFilename;
        contentType = 'application/text'; // .gd files are plain text
      } else { // zw
        content = generatedZWPacket;
        effectiveFilename = exportFilename.replace(/\.[^/.]+$/, "") + ".zw";
      }
      downloadFile(effectiveFilename, content, contentType);
    } catch (e) {
      alert(`Error during export preparation: ${e instanceof Error ? e.message : String(e)}`);
    }
  };

  const handleExportAllSchemas = () => {
    if (!activeProject || activeProject.schemas.length === 0) {
      alert("No schemas in the active project to export.");
      return;
    }
    const allSchemasContent = activeProject.schemas.map(s =>
      `# Schema Name: ${s.name}\n# Schema ID: ${s.id}\n${s.nlOrigin ? `# NL Origin: ${s.nlOrigin.replace(/\n/g, '\n#   ')}\n` : ''}${s.definition}\n///---END OF SCHEMA ${s.name}---\n\n`
    ).join('');
    downloadFile(exportAllFilename, allSchemasContent);
  };
  
  // --- Auto-completion Logic ---
  const ZW_KEYWORDS = [
      "ZW-REQUEST:", "ZW-RESPONSE:", "ZW-NARRATIVE-EVENT:", "ZW-NARRATIVE-SCENE:", "ZW-USER-PROFILE:", "ZW-SIMPLE-TASK:", "ZW-OBJECT:", "ZW-MATERIAL:", "ZW-LIGHT:", "ZW-CAMERA:",
      "CONTEXT:", "STATE-DELTA:", "META:", "ERROR:", "SCENE_GOAL:", "EVENT_ID:", "FOCUS:", "SETTING:", "LOCATION:", "TIME_OF_DAY:", "MOOD:", "CHARACTERS_INVOLVED:",
      "NAME:", "ROLE:", "CURRENT_EMOTION:", "SEQUENCE_PARTS:", "LABEL:", "EVENTS:", "SEQUENCE:", "TYPE:", "ACTION:", "ACTOR:", "TARGET:", "SFX_SUGGESTION:", "DESCRIPTION:", "ANCHOR:", "VFX_SUGGESTION:",
      "DIALOGUE:", "DIALOGUE_ID:", "CONTENT:", "EMOTION_TAG:", "DELIVERY_NOTE:", "OBJECTIVE_UPDATE:", "LINKED_QUEST:", "STATUS:", "OBJECTIVE_TEXT:",
      "AUTHOR:", "VERSION:", "SCENE_REFERENCE:", "TRIGGER_CONDITION:", "TAGS:", "QUESTS_STARTED:", "QUESTS_COMPLETED:", "ANCHORS_SET:", "PARAMS:", "SUB_TASKS:", "RESOURCES_REQUIRED:",
      "USER_ID:", "DISPLAY_NAME:", "EMAIL:", "AVATAR_URL:", "PREFERENCES:", "THEME:", "NOTIFICATIONS_ENABLED:", "LANGUAGE:", "ID:", "BASE_COLOR:", "METALLIC:", "ROUGHNESS:", "INTENSITY:", "POSITION:", "ROTATION:"
  ];

  const handleTemplateDefinitionChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const value = e.target.value;
    setTemplateDefinition(value);

    const cursorPos = e.target.selectionStart;
    const textBeforeCursor = value.substring(0, cursorPos);
    const currentLine = textBeforeCursor.split('\n').pop() || '';
    const currentWordMatch = currentLine.match(/(\S+)$/);
    const currentWord = currentWordMatch ? currentWordMatch[1] : '';

    if (currentWord.length > 1 && currentWord.toUpperCase().startsWith("ZW-")) {
        const filteredSuggestions = ZW_KEYWORDS.filter(keyword =>
            keyword.toLowerCase().startsWith(currentWord.toLowerCase())
        );
        setAutoCompleteSuggestions(filteredSuggestions);
        setShowAutoComplete(filteredSuggestions.length > 0);
        setActiveSuggestionIndex(0); 
        
        if (templateTextareaRef.current) {
            const textarea = templateTextareaRef.current;
            const style = window.getComputedStyle(textarea);
            const lineHeight = parseFloat(style.lineHeight) || (parseFloat(style.fontSize) * 1.2); 
            const linesBeforeCursor = textBeforeCursor.split('\n').length -1;

            const span = document.createElement('span');
            span.style.font = style.font;
            span.style.visibility = 'hidden';
            span.style.position = 'absolute';
            span.textContent = currentLine.substring(0, currentLine.lastIndexOf(currentWord));
            document.body.appendChild(span);
            const textWidthBeforeWord = span.offsetWidth;
            document.body.removeChild(span);

            setAutoCompletePosition({
                top: lineHeight * (linesBeforeCursor + 1) + textarea.offsetTop - textarea.scrollTop,
                left: textWidthBeforeWord + textarea.offsetLeft - textarea.scrollLeft + parseFloat(style.paddingLeft),
            });
        }

    } else {
        setShowAutoComplete(false);
    }
  };

  const handleSelectSuggestion = (suggestion: string) => {
      if (templateTextareaRef.current) {
          const textarea = templateTextareaRef.current;
          const value = textarea.value;
          const cursorPos = textarea.selectionStart;
          const textBeforeCursor = value.substring(0, cursorPos);
          const currentWordStart = textBeforeCursor.match(/(\S+)$/)?.index ?? cursorPos;
          
          const textAfterCursor = value.substring(cursorPos);

          const newValue = 
              value.substring(0, currentWordStart) + 
              suggestion + 
              textAfterCursor;
          
          setTemplateDefinition(newValue);
          setShowAutoComplete(false);
          
          setTimeout(() => {
              textarea.focus();
              textarea.setSelectionRange(currentWordStart + suggestion.length, currentWordStart + suggestion.length);
          }, 0);
      }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (showAutoComplete && autoCompleteSuggestions.length > 0) {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setActiveSuggestionIndex(prev => (prev + 1) % autoCompleteSuggestions.length);
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        setActiveSuggestionIndex(prev => (prev - 1 + autoCompleteSuggestions.length) % autoCompleteSuggestions.length);
      } else if (e.key === 'Enter' || e.key === 'Tab') {
        e.preventDefault();
        handleSelectSuggestion(autoCompleteSuggestions[activeSuggestionIndex]);
      } else if (e.key === 'Escape') {
        setShowAutoComplete(false);
      }
    }
  };

  // --- Asset Source & Engine Status Fetching ---
  const fetchAssetSourceStatuses = async () => {
    setIsFetchingAssetStatuses(true);
    setAssetSourceStatuses(prev => ({ 
        ...(prev || {}), 
        error: undefined, 
        lastFetched: prev?.lastFetched || new Date().toISOString() 
    }));
    try {
      const response = await fetch(MCP_ASSET_STATUS_ENDPOINT);
      if (response.ok) {
        let data;
        try {
            data = await response.json();
        } catch (jsonError) {
            console.error('[AssetStatus] JSON Parse error:', jsonError);
            setAssetSourceStatuses({ error: `Failed to parse asset status JSON response. ${jsonError instanceof Error ? jsonError.message : String(jsonError)}`, lastFetched: new Date().toISOString() });
            return;
        }
        
        // Normalize if daemon returns old flat structure
        if (data && !data.services && (data.polyhaven || data.sketchfab || data.internalLibrary || data.multi_engine_router)) {
            const { polyhaven, sketchfab, internalLibrary, multi_engine_router, ...rest } = data;
            const services: Record<string, AssetServiceStatusDetail> = {};
            if (polyhaven) services.polyhaven = polyhaven;
            if (sketchfab) services.sketchfab = sketchfab;
            if (internalLibrary) services.internalLibrary = internalLibrary;

            data = { services, multi_engine_router, ...rest };
        }
        setAssetSourceStatuses({ ...data, lastFetched: new Date().toISOString(), error: undefined });
      } else {
        const errorText = await response.text().catch(() => `Status: ${response.status}`);
        console.error('[AssetStatus] Fetch error response:', response.status, errorText);
        setAssetSourceStatuses({ error: `Failed to fetch asset statuses: ${response.status} ${errorText}`, lastFetched: new Date().toISOString() });
      }
    } catch (error) {
      console.error('[AssetStatus] Network error during fetch:', error);
      setAssetSourceStatuses({ error: `Network error fetching asset statuses: ${error instanceof Error ? error.message : String(error)}`, lastFetched: new Date().toISOString() });
    } finally {
      setIsFetchingAssetStatuses(false);
    }
  };

  const fetchEngineInfo = async () => {
    setIsFetchingEngineInfo(true);
    setEngineInfo(prev => ({ 
        ...(prev || {}),
        router_status: prev?.router_status, 
        capabilities: prev?.capabilities,
        timestamp: prev?.timestamp,
        error: undefined, 
        lastFetched: prev?.lastFetched || new Date().toISOString() 
    }));
    try {
      const response = await fetch(MCP_ENGINES_ENDPOINT);
      if (!response.ok) {
        const errorText = await response.text().catch(() => `Status Code: ${response.status}`);
        let detailedErrorMessage = `Server error ${response.status} (${response.statusText || 'Unknown Status'}) while fetching engine info. Server says: "${errorText}"`;
        
        if (response.status === 405) {
          detailedErrorMessage = `Error 405: Method Not Allowed for GET ${MCP_ENGINES_ENDPOINT}.\n\n` +
            `This usually means the backend server is not configured to accept GET requests on this path, OR there's a CORS preflight (OPTIONS) issue that wasn't resolved correctly.\n\n` +
            `Troubleshooting steps:\n` +
            `1. Verify the daemon's route definition for "/engines" (e.g., @app.get("/engines") in FastAPI).\n` +
            `2. Ensure the daemon is running the latest code and has been restarted.\n` +
            `3. Test with curl: curl -X GET -v ${MCP_ENGINES_ENDPOINT}\n` +
            `4. Check browser console Network tab for specific error details on both OPTIONS and GET requests.\n` +
            `5. Check if other GET endpoints on the daemon (e.g., ${MCP_DAEMON_BASE_URL}/ or ${MCP_ASSET_STATUS_ENDPOINT}) are working. If they are, the issue is specific to ${MCP_ENGINES_ENDPOINT}.`;
        }
        throw new Error(detailedErrorMessage);
      }
      let data: Omit<EnginesInfo, 'error' | 'lastFetched'>;
      try {
        data = await response.json();
      } catch (jsonError) {
        console.error('[EngineInfo] JSON Parse error:', jsonError);
        throw new Error(`Failed to parse engine info JSON response. ${jsonError instanceof Error ? jsonError.message : String(jsonError)}`);
      }
      setEngineInfo({ ...data, lastFetched: new Date().toISOString(), error: undefined });
    } catch (error) {
      console.error('[EngineInfo] Error during fetch:', error);
      const errorMessage = error instanceof Error ? error.message : String(error);
      setEngineInfo(prev => ({ ...prev, error: errorMessage, lastFetched: new Date().toISOString() }));
    } finally {
      setIsFetchingEngineInfo(false);
    }
  };


  // --- Render Functions ---
  const renderProjectsTab = () => (
    <div className="space-y-6">
      <section>
        <h2 className="text-xl font-semibold mb-3">Manage Projects</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
          <div>
            <label htmlFor="newProjectName" className="block text-sm font-medium mb-1">Project Name:</label>
            <input
              type="text"
              id="newProjectName"
              value={newProjectName}
              onChange={(e) => setNewProjectName(e.target.value)}
              placeholder="e.g., My Game Project"
              className="w-full p-2 border rounded"
            />
          </div>
          <div>
            <label htmlFor="newProjectDesc" className="block text-sm font-medium mb-1">Description:</label>
            <input
              type="text"
              id="newProjectDesc"
              value={newProjectDescription}
              onChange={(e) => setNewProjectDescription(e.target.value)}
              placeholder="Briefly describe the project"
              className="w-full p-2 border rounded"
            />
          </div>
        </div>
        <button onClick={handleCreateProject} className="action-button mr-2">Create New Project</button>
        <button onClick={handleLoadExampleTemplates} className="action-button secondary">Load Example Templates</button>
      </section>

      {projects.length > 0 && (
        <section>
          <h2 className="text-xl font-semibold mb-3">Available Projects</h2>
          <ul className="space-y-3">
            {projects.map(project => (
              <li key={project.id} className={`p-4 border rounded ${activeProjectId === project.id ? 'bg-blue-50 border-blue-300' : 'bg-white'}`}>
                <div className="flex justify-between items-center">
                  <div>
                    <h3 className="font-bold text-lg">{project.name}</h3>
                    <p className="text-sm text-gray-600">{project.description || "No description."}</p>
                    <p className="text-xs text-gray-500">Schemas: {project.schemas.length}</p>
                  </div>
                  <div className="space-x-2">
                    <button onClick={() => handleSetActiveProject(project.id)} className={`action-button text-sm ${activeProjectId === project.id ? 'opacity-50 cursor-default' : ''}`} disabled={activeProjectId === project.id}>
                      {activeProjectId === project.id ? 'Active' : 'Set Active'}
                    </button>
                    <button onClick={() => handleDeleteProject(project.id)} className="action-button secondary text-sm !bg-red-500 hover:!bg-red-700">Delete</button>
                  </div>
                </div>
                {activeProjectId === project.id && project.schemas.length > 0 && (
                  <div className="mt-3 pt-3 border-t">
                    <h4 className="font-semibold text-sm mb-2">Templates in this project:</h4>
                    <ul className="space-y-1">
                      {project.schemas.map(schema => (
                        <li key={schema.id} className="text-xs flex justify-between items-center p-1 hover:bg-gray-100 rounded">
                          <span>{schema.name}</span>
                          <div>
                            <button onClick={() => handleLoadSchema(schema)} className="link-button text-xs mr-2">Load</button>
                            <button onClick={() => handleDeleteSchema(schema.id)} className="link-button text-xs !text-red-500">Del</button>
                          </div>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );

  const renderCreateTab = () => (
    <div className="create-tab-content">
      <section className="template-designer-section">
        <h2 className="text-xl font-semibold mb-4">Template Designer {activeProject ? `(Project: ${activeProject.name})` : "(No Active Project)"}</h2>
        {!activeProject && (
          <p className="text-orange-600 bg-orange-50 p-3 rounded border border-orange-200 mb-4">
            <strong>Warning:</strong> No active project selected. Please go to the 'Projects' tab to create or select a project. 
            Templates can only be saved to an active project. You can still use the generator below.
          </p>
        )}
        <div className="mb-4">
            <label htmlFor="templateName" className="block text-sm font-medium mb-1">Template Name:</label>
            <input
                type="text"
                id="templateName"
                value={templateName}
                onChange={(e) => setTemplateName(e.target.value)}
                placeholder="e.g., ZW-PLAYER-CHARACTER"
                className="w-full p-2 border rounded"
                disabled={!activeProject}
            />
        </div>

        <div className="hybrid-editor-layout">
          <div className="code-editor-pane">
            <label htmlFor="templateDefinition" className="block text-sm font-medium mb-1">ZW Template Definition:</label>
            <div style={{ position: 'relative', flexGrow: 1 }}>
              <textarea
                id="templateDefinition"
                ref={templateTextareaRef}
                value={templateDefinition}
                onChange={handleTemplateDefinitionChange}
                onKeyDown={handleKeyDown}
                placeholder="Define your ZW template here using ZW syntax (e.g., ZW-TYPE:\n  KEY: value)"
                className="w-full h-full p-2 border rounded font-mono text-sm"
                aria-label="ZW Template Definition Input"
                spellCheck="false"
                disabled={!activeProject}
              />
              <AutoCompleteDropdown
                  suggestions={autoCompleteSuggestions}
                  show={showAutoComplete}
                  activeIndex={activeSuggestionIndex}
                  onSelectSuggestion={handleSelectSuggestion}
                  position={autoCompletePosition}
              />
            </div>
          </div>
          <div className="visual-pane">
            <div>
                <label className="block text-sm font-medium mb-1">Syntax Highlighted Preview:</label>
                <div className="relative">
                    <ZWSyntaxHighlighter zwString={templateDefinition} />
                    {activeProject && templateDefinition && (
                         <CopyButton textToCopy={templateDefinition} className="absolute top-2 right-2 action-button !p-1 !text-xs" buttonText="Copy" />
                    )}
                </div>
            </div>
            <div className="visual-preview-pane">
                <label className="block text-sm font-medium mb-1">Structural Visual Preview:</label>
                <ZWTemplateVisualizer templateDefinition={templateDefinition} />
            </div>
          </div>
        </div>
        <div className="mt-4">
            <button onClick={handleSaveSchemaToProject} className="action-button" disabled={!activeProject || !templateName || !templateDefinition}>Save Template to Project</button>
            <button onClick={handleNewTemplate} className="action-button secondary ml-2" disabled={!activeProject}>New Blank Template</button>
        </div>
        
        {currentSchemaNlOrigin && activeProject && (
             <div className="mt-4 p-3 bg-gray-50 border border-gray-200 rounded">
                <p className="text-xs text-gray-600"><strong>Original Natural Language for this template:</strong></p>
                <p className="text-xs text-gray-800 whitespace-pre-wrap"><em>{currentSchemaNlOrigin}</em></p>
             </div>
        )}

        {/* Comments Section */}
        {activeProject && templateIdToEdit && (
            <div className="mt-6 pt-4 border-t">
                <h3 className="text-md font-semibold mb-2">Comments for <span className="text-blue-600">{templateName || "this template"}</span>:</h3>
                <div className="space-y-2 mb-3 max-h-40 overflow-y-auto">
                    {schemaComments.map(comment => (
                        <div key={comment.id} className="text-xs p-2 bg-yellow-50 border border-yellow-200 rounded">
                            <p className="whitespace-pre-wrap">{comment.text}</p>
                            <div className="flex justify-between items-center mt-1">
                                <span className="text-gray-500">({new Date(comment.timestamp).toLocaleString()})</span>
                                <button onClick={() => handleDeleteComment(comment.id)} className="link-button !text-red-500 !text-xs">Delete</button>
                            </div>
                        </div>
                    ))}
                    {schemaComments.length === 0 && <p className="text-xs text-gray-500">No comments yet.</p>}
                </div>
                <textarea 
                    value={newCommentText} 
                    onChange={e => setNewCommentText(e.target.value)} 
                    placeholder="Add a comment..."
                    className="w-full p-2 border rounded text-xs mb-2"
                    rows={2}
                />
                <button onClick={handleAddComment} className="action-button !text-xs !py-1">Add Comment</button>
            </div>
        )}

      </section>

      <section className="natural-language-generator-section">
        <h2 className="text-xl font-semibold mb-4">Natural Language to ZW Packet Generator</h2>
        <div>
          <label htmlFor="nlScenario" className="block text-sm font-medium mb-1">Describe Scenario / Content:</label>
          <textarea
            id="nlScenario"
            value={nlScenario}
            onChange={(e) => setNlScenario(e.target.value)}
            placeholder="e.g., 'A red cube named 'MyBox' at position (1,2,3) with a shiny gold material and a spotlight on it.' OR a full narrative scene description."
            className="w-full p-2 border rounded font-mono text-sm"
            rows={4}
          />
           <div className="my-2">
                <label className="inline-flex items-center">
                    <input 
                        type="checkbox" 
                        checked={isNarrativeFocusEnabled} 
                        onChange={() => setIsNarrativeFocusEnabled(!isNarrativeFocusEnabled)}
                        className="form-checkbox h-4 w-4 text-blue-600"
                    />
                    <span className="ml-2 text-sm text-gray-700">Enable ZW-NARRATIVE-SCENE Focus (Detailed story structure)</span>
                </label>
            </div>
          <button onClick={handleGenerateZWFromNL} disabled={isGenerating || !ai} className="action-button">
            {isGenerating ? 'Generating...' : (ai ? 'Generate ZW Packet' : 'Gemini API Offline')}
          </button>
        </div>

        {generatedZWPacket && (
          <div className="mt-6">
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-lg font-semibold">Generated ZW Packet:</h3>
              <CopyButton textToCopy={generatedZWPacket} buttonText="Copy Packet" />
            </div>
            <ZWSyntaxHighlighter zwString={generatedZWPacket} />
            
            <div className="mt-4">
                 <label htmlFor="refinementSuggestion" className="block text-sm font-medium mb-1">Refine Generated Packet:</label>
                <input
                    type="text"
                    id="refinementSuggestion"
                    value={refinementSuggestion}
                    onChange={(e) => setRefinementSuggestion(e.target.value)}
                    placeholder="e.g., 'Change the cube's color to blue' or 'Add a TAG: important'"
                    className="w-full p-2 border rounded text-sm mb-2"
                />
                <button onClick={handleRefineZWFromNL} disabled={isGenerating || !ai} className="action-button secondary">
                    {isGenerating ? 'Refining...' : (ai ? 'Refine Packet' : 'Gemini API Offline')}
                </button>
            </div>

            <div className="mt-6">
              <label className="block text-sm font-medium mb-1">Blender Executable Path (for MCP Daemon):</label>
              <input
                type="text"
                value={blenderExecutablePath}
                onChange={(e) => setBlenderExecutablePath(e.target.value)}
                placeholder="e.g., /usr/bin/blender or C:\\Blender\\blender.exe"
                className="w-full p-2 border rounded text-sm"
              />
              <p className="text-xs text-gray-500 mt-1">If set, this path will be sent to the MCP Daemon. If empty, daemon uses its default.</p>
            </div>

            <button onClick={handleSendZwToMcp} disabled={isSendingToMcp || !generatedZWPacket} className="action-button mt-3 !bg-purple-600 hover:!bg-purple-700">
              {isSendingToMcp ? 'Processing...' : '⚡ Process with Multi-Engine Router'}
            </button>
            {mcpStatusMessage && (
              <div className="mt-3 p-3 bg-blue-50 border border-blue-200 rounded text-xs whitespace-pre-wrap">
                <h4 className="font-semibold text-sm mb-1">MCP Daemon Response:</h4>
                {mcpStatusMessage}
              </div>
            )}
          </div>
        )}
      </section>
    </div>
  );

  const renderValidationTab = () => (
     <div className="space-y-6">
        <section>
            <h2 className="text-xl font-semibold mb-3">Validate ZW Content</h2>
            <p className="text-sm text-gray-600 mb-3">
                Paste ZW content below or use the "Validate Editor Content" button to check the template currently in the Create tab.
                Project-specific validation rules (if defined in schema) are not yet implemented.
            </p>

            <label htmlFor="zwToValidate" className="block text-sm font-medium mb-1">ZW Content to Validate:</label>
            <textarea
                id="zwToValidate"
                value={zwToValidate}
                onChange={e => setZwToValidate(e.target.value)}
                rows={10}
                placeholder="Paste ZW content here..."
                className="w-full p-2 border rounded font-mono text-sm"
            />
            <div className="mt-3">
                <button onClick={handleValidateZwToValidateField} className="action-button">Validate Input Field</button>
                <button 
                    onClick={handleValidateCurrentEditor} 
                    className="action-button secondary ml-2"
                    disabled={!templateDefinition.trim()}
                >
                    Validate Editor Content
                </button>
            </div>
        </section>
        
        {validationFeedback.length > 0 && (
            <section>
                <h3 className="text-lg font-semibold mb-2">Validation Results:</h3>
                <div className="space-y-2">
                {validationFeedback.map((fb, index) => (
                    <div key={index} className={`p-3 rounded border text-sm
                        ${fb.type === 'success' ? 'bg-green-50 border-green-200 text-green-700' : ''}
                        ${fb.type === 'error' ? 'bg-red-50 border-red-200 text-red-700' : ''}
                        ${fb.type === 'warning' ? 'bg-yellow-50 border-yellow-200 text-yellow-700' : ''}
                        ${fb.type === 'info' ? 'bg-blue-50 border-blue-200 text-blue-700' : ''}
                    `}>
                        <p className="font-medium">{fb.message}</p>
                        {fb.details && fb.details.length > 0 && (
                            <ul className="list-disc list-inside pl-4 mt-1 text-xs">
                                {fb.details.map((d, i) => <li key={i}>{d}</li>)}
                            </ul>
                        )}
                         {fb.suggestions && fb.suggestions.length > 0 && (
                            <div className="mt-1">
                                <p className="text-xs font-semibold">Suggestions:</p>
                                <ul className="list-disc list-inside pl-4 text-xs">
                                    {fb.suggestions.map((s, i) => <li key={i}>{s}</li>)}
                                </ul>
                            </div>
                        )}
                    </div>
                ))}
                </div>
            </section>
        )}
     </div>
  );

  const renderVisualizeTab = () => (
    <div className="space-y-6">
      <section>
        <h2 className="text-xl font-semibold mb-3">Visualize ZW Structure</h2>
        <p className="text-sm text-gray-600 mb-3">
            Paste ZW content into the text area below to see its hierarchical structure.
            The visualizer helps understand nesting and relationships. You can also use content from the 'Create' tab.
        </p>
        <label htmlFor="zwToVisualize" className="block text-sm font-medium mb-1">ZW Content for Visualization:</label>
         <div className="relative">
            <textarea
                id="zwToVisualize"
                value={zwToVisualize}
                onChange={e => setZwToVisualize(e.target.value)}
                rows={12}
                placeholder="Paste ZW content here or use generated packet from Create tab."
                className="w-full p-2 border rounded font-mono text-sm"
            />
            <CopyButton textToCopy={zwToVisualize} className="absolute top-2 right-2 action-button !p-1 !text-xs" buttonText="Copy" />
        </div>
        <div className="mt-3">
             <button 
                onClick={() => setZwToVisualize(generatedZWPacket)} 
                className="action-button secondary"
                disabled={!generatedZWPacket.trim()}
            >
                Load from Generated Packet
            </button>
        </div>


        <div className="mt-4 p-4 border rounded bg-gray-50 min-h-[150px]">
          <ZWTemplateVisualizer templateDefinition={zwToVisualize} />
        </div>
      </section>

       <section>
        <h2 className="text-xl font-semibold mb-3">ZW ↔ JSON Round Trip Conversion</h2>
        <div className="grid md:grid-cols-2 gap-6">
            <div>
                <h3 className="text-lg font-medium mb-2">JSON to ZW</h3>
                <label htmlFor="jsonRootZwTypeInput" className="block text-sm font-medium mb-1">Root ZW Type (Optional):</label>
                <input
                    type="text"
                    id="jsonRootZwTypeInput"
                    value={jsonRootZwTypeInput}
                    onChange={(e) => setJsonRootZwTypeInput(e.target.value)}
                    placeholder="e.g., ZW-MY-DATA (defaults if empty)"
                    className="w-full p-2 border rounded text-sm mb-2"
                />
                <label htmlFor="jsonToConvertInput" className="block text-sm font-medium mb-1">JSON Input:</label>
                <textarea
                    id="jsonToConvertInput"
                    value={jsonToConvertInput}
                    onChange={(e) => setJsonToConvertInput(e.target.value)}
                    rows={8}
                    placeholder='{ "key": "value", "nested": { "sub_key": 123 } }'
                    className="w-full p-2 border rounded font-mono text-sm"
                />
                <button onClick={handleConvertJsonToZw} className="action-button mt-2">Convert JSON to ZW →</button>
            </div>
            <div>
                <h3 className="text-lg font-medium mb-2">ZW to JSON</h3>
                 <p className="text-xs text-gray-500 mb-2">Uses the ZW content from the Visualization field above.</p>
                <button onClick={handleConvertZwToVisualizeJson} className="action-button" disabled={!zwToVisualize.trim()}>← Convert ZW to JSON</button>
                <label htmlFor="visualizedZwAsJsonString" className="block text-sm font-medium mb-1 mt-2">JSON Output:</label>
                <div className="relative">
                    <textarea
                        id="visualizedZwAsJsonString"
                        value={visualizedZwAsJsonString}
                        readOnly
                        rows={10}
                        className="w-full p-2 border rounded font-mono text-sm bg-gray-100"
                    />
                    {visualizedZwAsJsonString && !visualizedZwAsJsonString.startsWith("//") && (
                        <CopyButton textToCopy={visualizedZwAsJsonString} className="absolute top-2 right-2 action-button !p-1 !text-xs" buttonText="Copy"/>
                    )}
                </div>
            </div>
        </div>
       </section>
    </div>
  );

  const renderExportTab = () => (
    <div className="space-y-6">
        <section>
            <h2 className="text-xl font-semibold mb-3">Export Generated ZW Packet</h2>
            {!generatedZWPacket.trim() && (
                <p className="text-orange-600 bg-orange-50 p-3 rounded border border-orange-200 mb-4">
                    No ZW packet has been generated yet. Please use the 'Create' tab to generate a ZW packet first.
                </p>
            )}
             <div className="mb-4">
                <label htmlFor="exportFilename" className="block text-sm font-medium mb-1">Filename for ZW/JSON export (e.g., my_packet.zw):</label>
                <input
                    type="text"
                    id="exportFilename"
                    value={exportFilename}
                    onChange={e => setExportFilename(e.target.value)}
                    className="w-full md:w-1/2 p-2 border rounded"
                    disabled={!generatedZWPacket.trim()}
                />
            </div>
            <div className="space-x-2">
                <button onClick={() => handleExportGeneratedPacket('zw')} className="action-button" disabled={!generatedZWPacket.trim()}>Export as .zw</button>
                <button onClick={() => handleExportGeneratedPacket('json')} className="action-button" disabled={!generatedZWPacket.trim()}>Export as .json</button>
            </div>
        </section>
        <section>
            <h2 className="text-xl font-semibold mb-3">Export ZW for Godot Engine</h2>
             <div className="mb-4">
                <label htmlFor="godotExportFilename" className="block text-sm font-medium mb-1">Filename for Godot script (e.g., my_schema.gd):</label>
                <input
                    type="text"
                    id="godotExportFilename"
                    value={godotExportFilename}
                    onChange={e => setGodotExportFilename(e.target.value)}
                    className="w-full md:w-1/2 p-2 border rounded"
                    disabled={!generatedZWPacket.trim()}
                />
            </div>
            <button onClick={() => handleExportGeneratedPacket('godot')} className="action-button" disabled={!generatedZWPacket.trim()}>Export as .gd (Godot Script)</button>
             <p className="text-xs text-gray-500 mt-2">
                This converts the ZW packet into a GDScript dictionary variable. The parser attempts to infer types.
            </p>
        </section>
        <section>
            <h2 className="text-xl font-semibold mb-3">Export All Schemas from Active Project</h2>
            {!activeProject || activeProject.schemas.length === 0 && (
                <p className="text-orange-600 bg-orange-50 p-3 rounded border border-orange-200 mb-4">
                   {activeProject ? "The current project has no schemas to export." : "No active project. Please select or create a project first."}
                </p>
            )}
            <div className="mb-4">
                <label htmlFor="exportAllFilename" className="block text-sm font-medium mb-1">Filename for project export (e.g., project_schemas.txt):</label>
                <input
                    type="text"
                    id="exportAllFilename"
                    value={exportAllFilename}
                    onChange={e => setExportAllFilename(e.target.value)}
                    className="w-full md:w-1/2 p-2 border rounded"
                    disabled={!activeProject || activeProject.schemas.length === 0}
                />
            </div>
            <button onClick={handleExportAllSchemas} className="action-button" disabled={!activeProject || activeProject.schemas.length === 0}>Export All Project Schemas</button>
        </section>
    </div>
  );

  const renderGuideTab = () => (
    <div className="space-y-6 text-sm">
        <section className="bg-blue-50 border border-blue-200 rounded-lg p-4">
            <h2 className="text-lg font-semibold mb-3 text-blue-700">🚀 Welcome to ZW Transformer v0.9.5</h2>
            <p className="mb-2">This tool is designed for creating, managing, and utilizing ZW (Ziegelwagga) consciousness patterns. ZW is a structured, human-readable data format optimized for AI interpretation, complex system state representation, and narrative design.</p>
            <p><strong>Current Focus: Multi-Engine Architecture & Template Design.</strong></p>
        </section>

        <section>
            <h3 className="text-md font-semibold mb-2">🧭 Recommended Workflow Pipeline:</h3>
            <div className="bg-gray-50 p-3 border rounded">
            <pre className="text-xs whitespace-pre-wrap bg-white p-2 border rounded">
{`graph TD
    A[📁 Projects: Create/Select Project] --> B{📝 Create Tab};
    B --> C[Define ZW Template Manually OR Use NL Generator];
    C --> D{Optional: Refine with AI};
    D --> E[⚡ Create: Process with Multi-Engine Router];
    E --> F[✨ Observe Results (e.g., Blender Output)];
    B --> G[✅ Validate Tab: Check ZW Syntax];
    B --> H[👁️ Visualize Tab: View Structure];
    B --> I[📤 Export Tab: Save ZW/JSON/GDScript];
    A --> J[📖 Guide: Review Workflow & Tips];
    E --> B; C --> B; D --> B; G --> B; H --> B; I --> B; F --> B;
`}
            </pre>
            <ol className="list-decimal list-inside space-y-1 mt-2 text-xs">
                <li><strong>Projects Tab:</strong> Start by creating a new project or selecting an existing one. Templates are saved within projects. Load example templates to get started.</li>
                <li><strong>Create Tab - Template Designer:</strong> Manually define your ZW template structure if you know the syntax. Use the syntax highlighter and structural visualizer. Save it to your active project.</li>
                <li><strong>Create Tab - NL Generator:</strong> Describe a scenario or data structure in natural language. The AI will attempt to generate a ZW packet. Enable "Narrative Focus" for detailed ZW-NARRATIVE-SCENE outputs. This packet can be further refined.</li>
                <li><strong>Create Tab - Process with Router:</strong> Send the generated ZW packet to the backend Multi-Engine Router. If Blender is targeted and configured, it will attempt to process the ZW data. Set your Blender executable path.</li>
                <li><strong>Validate Tab:</strong> Paste any ZW content to check its basic syntax validity.</li>
                <li><strong>Visualize Tab:</strong> View the hierarchical structure of a ZW packet or convert between ZW and JSON.</li>
                <li><strong>Export Tab:</strong> Export your generated ZW packets or all schemas from your active project.</li>
            </ol>
            </div>
        </section>

        <div className="grid md:grid-cols-2 gap-6">
            <section>
                <h3 className="text-md font-semibold mb-2">💡 Tips for Best Results</h3>
                <ul className="list-disc list-inside space-y-1 bg-yellow-50 p-3 border border-yellow-200 rounded text-xs">
                    <li><strong>Be Specific (NL Gen):</strong> The more detail you provide in natural language, the better the AI can structure the ZW.</li>
                    <li><strong>Narrative Focus:</strong> Use for story beats, dialogues, and scene descriptions. Provides richer ZW-NARRATIVE-SCENE.</li>
                    <li><strong>Iterate:</strong> Generate, review, refine. Use the AI refiner or manually edit ZW packets.</li>
                    <li><strong>Project Templates:</strong> When using the NL generator, it will try to use schemas from your active project if they match the scenario.</li>
                    <li><strong>Valid Root Types:</strong> All ZW packets MUST start with a root type declaration (e.g., \`ZW-REQUEST:\`).</li>
                     <li><strong>Configure Blender Path:</strong> In the 'Create' tab, set the path to your Blender executable if you want to use the MCP daemon for 3D processing. If left empty, the daemon will try its default path.</li>
                </ul>
            </section>
            <section>
                <h3 className="text-md font-semibold mb-2">🔍 Basic ZW Syntax Quick Reference</h3>
                <div className="bg-gray-50 p-3 border rounded text-xs">
                    <p><strong>Root Type:</strong> \`ZW-MY-TYPE:\` (Must be first line, ends with colon)</p>
                    <p><strong>Key-Value:</strong> \`  KEY: Value\` (Indented, colon separated)</p>
                    <p><strong>Sections:</strong> \`  SECTION_NAME:\` (Indented, ends with colon, children are further indented)</p>
                    <p><strong>Lists:</strong> \`  - ListItem1\` (Indented, starts with hyphen-space)</p>
                    <p><strong>List of Key-Values:</strong><br/>\`  - KEY_IN_LIST: Value\`</p>
                    <p><strong>Comments:</strong> \`  # This is a comment\`</p>
                    <p><strong>Multi-line Strings:</strong> <br/>\`  DESCRIPTION: This is a long...\`<br/>\`    ...description that continues.\`</p>
                </div>
            </section>
        </div>
        
        <section>
            <h3 className="text-md font-semibold mb-2">Daemon Status <button onClick={() => { fetchAssetSourceStatuses(); fetchEngineInfo(); }} className="link-button text-xs">(Refresh All)</button></h3>
            <div className="grid md:grid-cols-2 gap-6">
                <div>
                    <h4 className="font-medium text-sm mb-1">Asset Source Statuses</h4>
                    <div className="p-3 border rounded bg-gray-50 space-y-2 text-xs min-h-[100px]">
                    {isFetchingAssetStatuses && <p><em>Fetching asset statuses...</em></p>}
                    {!isFetchingAssetStatuses && !assetSourceStatuses && <p className="text-red-500">Could not fetch asset statuses. Is the daemon running at {MCP_ASSET_STATUS_ENDPOINT}?</p>}
                    {!isFetchingAssetStatuses && assetSourceStatuses?.error && <p className="text-red-500 whitespace-pre-wrap">Error: {assetSourceStatuses.error}</p>}
                    {!isFetchingAssetStatuses && assetSourceStatuses && !assetSourceStatuses.error && (
                        <>
                            {assetSourceStatuses.services?.polyhaven && (
                                <p>Polyhaven: <span className={assetSourceStatuses.services.polyhaven.enabled ? 'text-green-600' : 'text-red-600'}>{assetSourceStatuses.services.polyhaven.message}</span></p>
                            )}
                            {assetSourceStatuses.services?.sketchfab && (
                                <p>Sketchfab: <span className={assetSourceStatuses.services.sketchfab.enabled ? 'text-green-600' : 'text-yellow-600'}>{assetSourceStatuses.services.sketchfab.message}</span></p>
                            )}
                             {assetSourceStatuses.services?.internalLibrary && (
                                <p>Internal Library: <span className={assetSourceStatuses.services.internalLibrary.enabled ? 'text-green-600' : 'text-red-600'}>{assetSourceStatuses.services.internalLibrary.message}</span></p>
                            )}
                            {/* Display for multi_engine_router if it's within assetSourceStatuses (e.g., from a legacy endpoint) */}
                            {assetSourceStatuses.multi_engine_router && (
                                <div className="pt-2 mt-2 border-t">
                                    <p className="font-semibold">Multi-Engine Router (via Asset Status):</p>
                                    <p className="pl-2">Status: <span className={assetSourceStatuses.multi_engine_router.enabled ? 'text-green-600' : 'text-red-600'}>{assetSourceStatuses.multi_engine_router.message}</span></p>
                                    <p className="pl-2">Registered Engines: {assetSourceStatuses.multi_engine_router.registered_engines ?? 'N/A'}</p>
                                    <p className="pl-2">Default Engine: {assetSourceStatuses.multi_engine_router.default_engine ?? 'N/A'}</p>
                                </div>
                            )}
                            {assetSourceStatuses.timestamp && <p className="text-gray-500 mt-1">Last Updated: {new Date(assetSourceStatuses.timestamp).toLocaleString()}</p>}
                        </>
                    )}
                    </div>
                </div>
                <div>
                    <h4 className="font-medium text-sm mb-1">Registered Engines & Capabilities</h4>
                     <div className="p-3 border rounded bg-gray-50 space-y-2 text-xs min-h-[100px]">
                        {isFetchingEngineInfo && <p><em>Loading engine information...</em></p>}
                        
                        {!isFetchingEngineInfo && engineInfo?.error && (
                            <div className="text-red-500 whitespace-pre-wrap">
                                {engineInfo.error.includes("Error 405") ? (
                                    <>
                                        <p className="font-semibold">Backend Configuration Issue (Error 405):</p>
                                        <p>The server at <code>{MCP_ENGINES_ENDPOINT}</code> is not allowing GET requests.</p>
                                        <div className="mt-2 text-xs">{engineInfo.error.substring(engineInfo.error.indexOf("Troubleshooting steps:"))}</div>
                                    </>
                                ) : (
                                    <>
                                        <p className="font-semibold">Error fetching engine info:</p>
                                        {engineInfo.error}
                                    </>
                                )}
                            </div>
                        )}

                        {!isFetchingEngineInfo && !engineInfo?.error && engineInfo?.router_status && engineInfo.router_status.engines && (
                            <>
                                <p>Total Engines: <strong>{engineInfo.router_status.registered_engines}</strong> | Default: <strong>{engineInfo.router_status.default_engine || 'N/A'}</strong></p>
                                {Object.values(engineInfo.router_status.engines).map(engine => (
                                    <div key={engine.name} className="pt-1 mt-1 border-t">
                                        <p className="font-semibold">{engine.name} <span className="text-gray-500 text-xs">(v{engine.version})</span> - Status: <span className={engine.status === 'active' ? 'text-green-600' : 'text-red-600'}>{engine.status}</span></p>
                                        <p className="pl-2">Capabilities: {engine.capabilities.map(c => `ZW-${String(c).toUpperCase()}`).join(', ') || "None listed"}</p>
                                    </div>
                                ))}
                                {engineInfo.timestamp && <p className="text-gray-500 mt-1">Last Updated: {new Date(engineInfo.timestamp).toLocaleString()}</p>}
                            </>
                        )}
                        {!isFetchingEngineInfo && !engineInfo?.error && !engineInfo?.router_status && (
                            <p>No engine information available. Ensure daemon is running and GET {MCP_ENGINES_ENDPOINT} is accessible.</p>
                        )}
                    </div>
                </div>
            </div>
        </section>

    </div>
  );


  // --- Main Render ---
  return (
    <div className="app-container">
      <header>ZW Transformer <span style={{fontSize: '0.6em', color: '#bdc3c7'}}>v0.9.5</span></header>
      <nav role="navigation" aria-label="Main navigation" className="tabs">
        {(['projects', 'create', 'validate', 'visualize', 'export', 'library', 'guide'] as TabKey[]).map(key => (
          <button
            key={key}
            className={activeTab === key ? 'active' : ''}
            onClick={() => setActiveTab(key)}
            aria-pressed={activeTab === key}
            disabled={key === 'library' /* Enable projects later: || key === 'projects' */} 
          >
            {key.charAt(0).toUpperCase() + key.slice(1)}
          </button>
        ))}
      </nav>
      <main className="tab-content">
        {activeTab === 'projects' && renderProjectsTab()}
        {activeTab === 'create' && renderCreateTab()}
        {activeTab === 'validate' && renderValidationTab()}
        {activeTab === 'visualize' && renderVisualizeTab()}
        {activeTab === 'export' && renderExportTab()}
        {activeTab === 'library' && <p>Feature Coming Soon: Shared ZW Template Library.</p>}
        {activeTab === 'guide' && renderGuideTab()}
      </main>
      <footer role="contentinfo">
        <p>&copy; {new Date().getFullYear()} ZW Transformer Project. Consciousness Interface Designer.</p>
        <p>Supports Multi-Engine Architecture. Current focus: Blender 3D and ZW Template Design.</p>
      </footer>
    </div>
  );
};

const container = document.getElementById('root');
if (container) {
  const root = createRoot(container);
  root.render(<App />);
} else {
  console.error("Failed to find the root element for React application.");
}

export default App;
