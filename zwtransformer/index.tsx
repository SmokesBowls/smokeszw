import React, { useState, useEffect, useRef } from 'react';
import { createRoot } from 'react-dom/client';
import ZWTemplateVisualizer from './ZWTemplateVisualizer';
import ZWSyntaxHighlighter from './ZWSyntaxHighlighter';
import zwToJson from './zwToJson';
import jsonToZw from './jsonToZw';
import zwToGodotScript from './zwToGodotScript';
import { validateZWContent } from './zwParser';

// === CONSTANTS ===
const API_BASE = 'http://localhost:1111';
const API_ENDPOINTS = {
  processZw: `${API_BASE}/process_zw`,
  assetStatus: `${API_BASE}/asset_source_statuses`,
  engines: `${API_BASE}/engines`,
  health: `${API_BASE}/health`,
  ollamaModels: `${API_BASE}/ollama/models`,
  ollamaGenerate: `${API_BASE}/ollama/generate`,
  ollamaRefine: `${API_BASE}/ollama/refine`
};

// === INTERFACES ===
interface AssetSourceStatuses {
  services: {
    polyhaven: { enabled: boolean; message: string; api_version?: string };
    sketchfab: { enabled: boolean; message: string; last_sync?: string };
    internalLibrary: { enabled: boolean; message: string; entries?: number };
  };
  timestamp: string;
  multi_engine_router?: {
    registered_engines: number;
    default_engine: string;
    engines: Record<string, EngineDetail>;
    total_capabilities: number;
  };
}

interface EngineDetail {
  name: string;
  version: string;
  capabilities: string[];
  status: string;
}

interface EnginesInfo {
  router_status: {
    registered_engines: number;
    default_engine: string;
    engines: Record<string, EngineDetail>;
    total_capabilities: number;
  };
  capabilities: Record<string, string[]>;
  timestamp: string;
  error?: string;
  lastFetched?: string;
}

interface OllamaModelsResponse {
  status: string;
  models: string[];
  count: number;
  timestamp: string;
  message?: string;
}

// === MAIN COMPONENT ===
const ZWTransformer: React.FC = () => {
  // === STATE ===
  const [activeTab, setActiveTab] = useState<string>('projects');
  const [projects, setProjects] = useState<any[]>([]);
  const [selectedProject, setSelectedProject] = useState<any>(null);
  const [zwContent, setZwContent] = useState<string>('');
  const [naturalLanguageInput, setNaturalLanguageInput] = useState<string>('');
  const [validationResults, setValidationResults] = useState<any>(null);
  const [jsonOutput, setJsonOutput] = useState<string>('');
  const [godotOutput, setGodotOutput] = useState<string>('');
  const [assetSourceStatuses, setAssetSourceStatuses] = useState<AssetSourceStatuses | null>(null);
  const [engineInfo, setEngineInfo] = useState<EnginesInfo | null>(null);
  const [isFetchingEngineInfo, setIsFetchingEngineInfo] = useState<boolean>(false);
  const [blenderExecutablePath, setBlenderExecutablePath] = useState<string>('');
  const [processingMessage, setProcessingMessage] = useState<string>('');
  
  // === OLLAMA STATE ===
  const [ollamaModels, setOllamaModels] = useState<string[]>([]);
  const [selectedModel, setSelectedModel] = useState<string>('');
  const [ollamaStatus, setOllamaStatus] = useState<'connected' | 'disconnected' | 'checking'>('checking');
  const [isFetchingModels, setIsFetchingModels] = useState<boolean>(false);
  const [isGenerating, setIsGenerating] = useState<boolean>(false);
  const [narrativeFocus, setNarrativeFocus] = useState<boolean>(true);
  const [generationHistory, setGenerationHistory] = useState<string[]>([]);
  const [refinementSuggestion, setRefinementSuggestion] = useState<string>('');

  // === REFS ===
  const zwContentRef = useRef<HTMLTextAreaElement>(null);

  // === EFFECTS ===
  useEffect(() => {
    // Load saved data
    const savedBlenderPath = localStorage.getItem('zwt_blender_path');
    if (savedBlenderPath) setBlenderExecutablePath(savedBlenderPath);

    const savedModel = localStorage.getItem('zwt_selected_model');
    if (savedModel) setSelectedModel(savedModel);

    const savedNarrativeFocus = localStorage.getItem('zwt_narrative_focus');
    if (savedNarrativeFocus) setNarrativeFocus(savedNarrativeFocus === 'true');

    // Fetch initial data
    fetchAssetSourceStatuses();
    fetchEngineInfo();
    fetchOllamaModels();
  }, []);

  useEffect(() => {
    if (blenderExecutablePath) {
      localStorage.setItem('zwt_blender_path', blenderExecutablePath);
    }
  }, [blenderExecutablePath]);

  useEffect(() => {
    if (selectedModel) {
      localStorage.setItem('zwt_selected_model', selectedModel);
    }
  }, [selectedModel]);

  useEffect(() => {
    localStorage.setItem('zwt_narrative_focus', narrativeFocus.toString());
  }, [narrativeFocus]);

  // === OLLAMA FUNCTIONS ===
  const fetchOllamaModels = async () => {
    setIsFetchingModels(true);
    setOllamaStatus('checking');
    
    try {
      const response = await fetch(API_ENDPOINTS.ollamaModels);
      const data: OllamaModelsResponse = await response.json();
      
      if (data.status === 'success' && data.models) {
        setOllamaModels(data.models);
        setOllamaStatus('connected');
        
        // Set default model if none selected
        if (!selectedModel && data.models.length > 0) {
          // Prefer dolphin-mistral if available, otherwise first model
          const preferredModel = data.models.find(m => m.includes('dolphin-mistral')) || data.models[0];
          setSelectedModel(preferredModel);
        }
      } else {
        setOllamaModels([]);
        setOllamaStatus('disconnected');
      }
    } catch (error) {
      console.error('Failed to fetch Ollama models:', error);
      setOllamaModels([]);
      setOllamaStatus('disconnected');
    } finally {
      setIsFetchingModels(false);
    }
  };

  const handleGenerateZWFromNL = async () => {
    if (!naturalLanguageInput.trim()) return;
    if (!selectedModel) {
      alert('Please select an Ollama model first');
      return;
    }

    setIsGenerating(true);
    setProcessingMessage(`Generating ZW with ${selectedModel}...`);

    try {
      const response = await fetch(API_ENDPOINTS.ollamaGenerate, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model: selectedModel,
          scenario: naturalLanguageInput,
          narrative_focus: narrativeFocus,
          project_templates: selectedProject?.templates || []
        })
      });

      const data = await response.json();
      
      if (data.status === 'success') {
        setZwContent(data.generated_zw);
        setGenerationHistory(prev => [naturalLanguageInput, ...prev.slice(0, 4)]);
        setProcessingMessage(`✅ Generated with ${data.model_used}`);
        
        // Auto-validate the generated content
        const validation = validateZWContent(data.generated_zw);
        setValidationResults(validation);
      } else {
        setProcessingMessage(`❌ Generation failed: ${data.message}`);
      }
    } catch (error) {
      console.error('Generation error:', error);
      setProcessingMessage('❌ Failed to connect to Ollama');
    } finally {
      setIsGenerating(false);
      setTimeout(() => setProcessingMessage(''), 3000);
    }
  };

  const handleRefineZWContent = async () => {
    if (!zwContent.trim() || !refinementSuggestion.trim()) return;
    if (!selectedModel) {
      alert('Please select an Ollama model first');
      return;
    }

    setIsGenerating(true);
    setProcessingMessage(`Refining ZW with ${selectedModel}...`);

    try {
      const response = await fetch(API_ENDPOINTS.ollamaRefine, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model: selectedModel,
          current_zw: zwContent,
          refinement_suggestion: refinementSuggestion
        })
      });

      const data = await response.json();
      
      if (data.status === 'success') {
        setZwContent(data.refined_zw);
        setRefinementSuggestion('');
        setProcessingMessage(`✅ Refined with ${data.model_used}`);
        
        // Auto-validate the refined content
        const validation = validateZWContent(data.refined_zw);
        setValidationResults(validation);
      } else {
        setProcessingMessage(`❌ Refinement failed: ${data.message}`);
      }
    } catch (error) {
      console.error('Refinement error:', error);
      setProcessingMessage('❌ Failed to connect to Ollama');
    } finally {
      setIsGenerating(false);
      setTimeout(() => setProcessingMessage(''), 3000);
    }
  };

  // === API FUNCTIONS ===
  const fetchAssetSourceStatuses = async () => {
    try {
      const response = await fetch(API_ENDPOINTS.assetStatus);
      const data = await response.json();
      setAssetSourceStatuses(data);
    } catch (error) {
      console.error('Failed to fetch asset source statuses:', error);
    }
  };

  const fetchEngineInfo = async () => {
    setIsFetchingEngineInfo(true);
    try {
      const response = await fetch(API_ENDPOINTS.engines);
      const data = await response.json();
      setEngineInfo({
        ...data,
        lastFetched: new Date().toLocaleTimeString()
      });
    } catch (error) {
      console.error('Failed to fetch engine info:', error);
      setEngineInfo({
        router_status: {
          registered_engines: 0,
          default_engine: 'none',
          engines: {},
          total_capabilities: 0
        },
        capabilities: {},
        timestamp: new Date().toISOString(),
        error: `Failed to connect to daemon: ${error instanceof Error ? error.message : 'Unknown error'}`,
        lastFetched: new Date().toLocaleTimeString()
      });
    } finally {
      setIsFetchingEngineInfo(false);
    }
  };

  const handleSendZwToMcp = async () => {
    if (!zwContent.trim()) return;

    setProcessingMessage('Processing ZW with multi-engine router...');

    try {
      const payload: any = {
        zw_data: zwContent,
        route_to_blender: true
      };

      if (blenderExecutablePath) {
        payload.blender_path = blenderExecutablePath;
      }

      const response = await fetch(API_ENDPOINTS.processZw, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      const responseData = await response.json();

      if (responseData.status === 'processed' && responseData.results) {
        const results = responseData.results;
        const successCount = Object.values(results).filter((r: any) => r.status === 'success').length;
        const totalEngines = Object.keys(results).length;
        
        let message = `✅ Multi-engine processing complete! ${successCount}/${totalEngines} engines succeeded.\n\n`;
        
        Object.entries(results).forEach(([engine, result]: [string, any]) => {
          if (result.status === 'success') {
            message += `🟢 ${engine}: `;
            if (result.blender_results && result.blender_results.length > 0) {
              message += `Created ${result.blender_results.length} objects\n`;
            } else {
              message += `Processed successfully\n`;
            }
          } else {
            message += `🔴 ${engine}: ${result.message || 'Failed'}\n`;
          }
        });
        
        setProcessingMessage(message);
      } else {
        setProcessingMessage(`❌ Processing failed: ${responseData.message || 'Unknown error'}`);
      }
    } catch (error) {
      console.error('MCP processing error:', error);
      setProcessingMessage('❌ Failed to connect to MCP daemon');
    }

    setTimeout(() => setProcessingMessage(''), 5000);
  };

  // === UTILITY FUNCTIONS ===
  const handleValidateZW = () => {
    const results = validateZWContent(zwContent);
    setValidationResults(results);
  };

  const handleConvertToJson = () => {
    try {
      const json = zwToJson(zwContent);
      setJsonOutput(JSON.stringify(json, null, 2));
    } catch (error) {
      setJsonOutput(`Error: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  };

  const handleConvertToGodot = () => {
    try {
      const script = zwToGodotScript(zwContent);
      setGodotOutput(script);
    } catch (error) {
      setGodotOutput(`Error: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  };

  // === RENDER FUNCTIONS ===
  const renderOllamaStatus = () => (
    <div className="mb-4 p-3 border rounded-lg bg-gray-50">
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <span className={`w-3 h-3 rounded-full ${
            ollamaStatus === 'connected' ? 'bg-green-500' : 
            ollamaStatus === 'disconnected' ? 'bg-red-500' : 'bg-yellow-500'
          }`}></span>
          <span className="font-medium">
            {ollamaStatus === 'connected' ? '✅ Connected to Ollama' :
             ollamaStatus === 'disconnected' ? '❌ Ollama Disconnected' : '🔄 Checking...'}
          </span>
        </div>
        <button
          onClick={fetchOllamaModels}
          disabled={isFetchingModels}
          className="px-3 py-1 text-sm bg-blue-500 text-white rounded hover:bg-blue-600 disabled:opacity-50"
        >
          {isFetchingModels ? '🔄' : '🔄 Refresh'}
        </button>
      </div>
      
      {ollamaStatus === 'disconnected' && (
        <div className="mt-2 text-sm text-red-600">
          <p>Make sure Ollama is running:</p>
          <code className="block mt-1 p-2 bg-gray-100 rounded">ollama serve</code>
        </div>
      )}
      
      {ollamaStatus === 'connected' && ollamaModels.length > 0 && (
        <div className="mt-3">
          <label className="block text-sm font-medium mb-2">🤖 Select AI Model ({ollamaModels.length} available):</label>
          <select
            value={selectedModel}
            onChange={(e) => setSelectedModel(e.target.value)}
            className="w-full px-3 py-2 border rounded-md"
          >
            <option value="">Choose a model...</option>
            {ollamaModels.map(model => (
              <option key={model} value={model}>{model}</option>
            ))}
          </select>
        </div>
      )}
    </div>
  );

  const renderCreateTab = () => (
    <div className="space-y-6">
      <div className="bg-white p-6 rounded-lg shadow">
        <h3 className="text-xl font-semibold mb-4">🤖 AI-Powered ZW Generation</h3>
        
        {renderOllamaStatus()}
        
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-2">Natural Language Scenario:</label>
            <textarea
              value={naturalLanguageInput}
              onChange={(e) => setNaturalLanguageInput(e.target.value)}
              placeholder="Describe your scene... e.g., 'A brave knight discovers a magical sword in an ancient temple'"
              className="w-full px-3 py-2 border rounded-md h-24"
            />
          </div>

          <div className="flex items-center space-x-4">
            <label className="flex items-center">
              <input
                type="checkbox"
                checked={narrativeFocus}
                onChange={(e) => setNarrativeFocus(e.target.checked)}
                className="mr-2"
              />
              🎭 Narrative Focus Mode
            </label>
          </div>

          <div className="flex space-x-2">
            <button
              onClick={handleGenerateZWFromNL}
              disabled={!naturalLanguageInput.trim() || !selectedModel || isGenerating}
              className="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700 disabled:opacity-50"
            >
              {isGenerating ? '🔄 Generating...' : '✨ Generate ZW'}
            </button>
            
            {selectedModel && (
              <span className="px-3 py-2 bg-blue-100 text-blue-800 rounded text-sm">
                Using: {selectedModel}
              </span>
            )}
          </div>

          {generationHistory.length > 0 && (
            <div>
              <label className="block text-sm font-medium mb-2">Recent Generations:</label>
              <div className="space-y-1">
                {generationHistory.map((item, idx) => (
                  <button
                    key={idx}
                    onClick={() => setNaturalLanguageInput(item)}
                    className="block w-full text-left px-3 py-1 text-sm bg-gray-100 rounded hover:bg-gray-200"
                  >
                    {item}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="bg-white p-6 rounded-lg shadow">
        <h3 className="text-xl font-semibold mb-4">📝 ZW Content Editor</h3>
        <textarea
          ref={zwContentRef}
          value={zwContent}
          onChange={(e) => setZwContent(e.target.value)}
          placeholder="Your ZW content will appear here..."
          className="w-full px-3 py-2 border rounded-md font-mono text-sm h-64"
        />
        
        {zwContent && (
          <div className="mt-4 space-y-3">
            <div>
              <label className="block text-sm font-medium mb-2">🔧 Refinement Suggestion:</label>
              <input
                type="text"
                value={refinementSuggestion}
                onChange={(e) => setRefinementSuggestion(e.target.value)}
                placeholder="e.g., 'Add more emotional depth' or 'Make it more action-oriented'"
                className="w-full px-3 py-2 border rounded-md"
              />
            </div>
            
            <div className="flex space-x-2">
              <button
                onClick={handleRefineZWContent}
                disabled={!refinementSuggestion.trim() || !selectedModel || isGenerating}
                className="px-4 py-2 bg-purple-600 text-white rounded hover:bg-purple-700 disabled:opacity-50"
              >
                {isGenerating ? '🔄 Refining...' : '🎨 Refine ZW'}
              </button>
              
              <button
                onClick={handleValidateZW}
                className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
              >
                ✅ Validate
              </button>
            </div>
          </div>
        )}
      </div>

      <div className="bg-white p-6 rounded-lg shadow">
        <h3 className="text-xl font-semibold mb-4">⚡ Multi-Engine Processing</h3>
        
        <div className="mb-4">
          <label className="block text-sm font-medium mb-2">
            🎨 Blender Executable Path (Optional)
          </label>
          <input
            type="text"
            value={blenderExecutablePath}
            onChange={(e) => setBlenderExecutablePath(e.target.value)}
            placeholder="e.g., /home/user/blender-4.4.3/blender"
            className="w-full px-3 py-2 border rounded-md"
          />
          <p className="text-xs text-gray-500 mt-1">
            Leave empty to use system default. Path to your Blender executable.
          </p>
        </div>

        <button
          onClick={handleSendZwToMcp}
          disabled={!zwContent.trim()}
          className="px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700 disabled:opacity-50"
        >
          ⚡ Process with Multi-Engine Router
        </button>
      </div>

      {processingMessage && (
        <div className="bg-blue-50 border border-blue-200 p-4 rounded-lg">
          <pre className="text-sm whitespace-pre-wrap">{processingMessage}</pre>
        </div>
      )}
    </div>
  );

  const renderGuideTab = () => (
    <div className="space-y-6">
      <div className="bg-white p-6 rounded-lg shadow">
        <h3 className="text-xl font-semibold mb-4">📖 ZW Transformer Guide</h3>
        
        <div className="space-y-4">
          <div>
            <h4 className="font-semibold text-lg">🤖 AI Model Selection</h4>
            <p className="text-gray-600">Choose the right model for your task:</p>
            <ul className="mt-2 space-y-1 text-sm">
              <li><strong>dolphin-mistral:</strong> Best for creative narrative content</li>
              <li><strong>deepseek-r1:</strong> Highest quality, complex scenarios</li>
              <li><strong>llama3:</strong> Balanced speed and quality</li>
              <li><strong>deepseek-coder:</strong> Fast, structured content</li>
            </ul>
          </div>

          <div>
            <h4 className="font-semibold text-lg">🎭 Narrative Focus Mode</h4>
            <p className="text-gray-600">
              When enabled, generates ZW-NARRATIVE-SCENE packets optimized for cinematic game scripting and story management.
            </p>
          </div>

          <div>
            <h4 className="font-semibold text-lg">⚡ Multi-Engine Processing</h4>
            <p className="text-gray-600">
              Send your ZW content to multiple game engines simultaneously. Currently supports Blender with Godot coming soon.
            </p>
          </div>
        </div>
      </div>

      {/* Engine Status */}
      <div className="bg-white p-6 rounded-lg shadow">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-xl font-semibold">🚀 Multi-Engine Router Status</h3>
          <button
            onClick={fetchEngineInfo}
            disabled={isFetchingEngineInfo}
            className="px-3 py-1 text-sm bg-blue-500 text-white rounded hover:bg-blue-600 disabled:opacity-50"
          >
            {isFetchingEngineInfo ? '🔄' : '🔄 Refresh'}
          </button>
        </div>

        {isFetchingEngineInfo ? (
          <p>Loading engine information...</p>
        ) : engineInfo?.error ? (
          <div className="text-red-600">
            <p><strong>❗ Connection Error:</strong> {engineInfo.error}</p>
            <div className="mt-2 text-sm">
              <p>Troubleshooting steps:</p>
              <ol className="list-decimal ml-4 mt-1">
                <li>Ensure the daemon is running: <code>python zw_transformer_daemon.py</code></li>
                <li>Check if the /engines route exists in your daemon</li>
                <li>Verify the daemon is accessible at http://localhost:1111</li>
                <li>Test manually: <code>curl http://localhost:1111/engines</code></li>
              </ol>
            </div>
          </div>
        ) : engineInfo ? (
          <div>
            <div className="grid grid-cols-2 gap-4 mb-4">
              <div className="bg-gray-50 p-3 rounded">
                <div className="text-2xl font-bold text-green-600">{engineInfo.router_status.registered_engines}</div>
                <div className="text-sm text-gray-600">Registered Engines</div>
              </div>
              <div className="bg-gray-50 p-3 rounded">
                <div className="text-2xl font-bold text-blue-600">{engineInfo.router_status.total_capabilities}</div>
                <div className="text-sm text-gray-600">Total Capabilities</div>
              </div>
            </div>
            
            <div className="text-sm text-gray-500 mb-3">
              Last updated: {engineInfo.lastFetched} | Default engine: {engineInfo.router_status.default_engine}
            </div>

            <h4 className="font-semibold mb-2">Registered Engines & Capabilities:</h4>
            <div className="space-y-2">
              {Object.entries(engineInfo.router_status.engines).map(([engineName, engineDetail]) => (
                <div key={engineName} className="border rounded p-3">
                  <div className="flex items-center justify-between mb-2">
                    <h5 className="font-medium">{engineDetail.name}</h5>
                    <span className={`px-2 py-1 rounded text-xs ${
                      engineDetail.status === 'active' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
                    }`}>
                      {engineDetail.status}
                    </span>
                  </div>
                  <div className="text-sm text-gray-600 mb-2">Version: {engineDetail.version}</div>
                  <div className="flex flex-wrap gap-1">
                    {engineDetail.capabilities.map((capability) => (
                      <span key={capability} className="px-2 py-1 bg-blue-100 text-blue-700 rounded text-xs">
                        ZW-{String(capability).toUpperCase()}
                      </span>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        ) : (
          <p>No engine information available.</p>
        )}
      </div>

      {/* Asset Source Status */}
      <div className="bg-white p-6 rounded-lg shadow">
        <h3 className="text-xl font-semibold mb-4">🎨 External Asset Source Statuses</h3>
        {assetSourceStatuses ? (
          <div className="space-y-2">
            {Object.entries(assetSourceStatuses.services).map(([source, status]) => (
              <div key={source} className="flex items-center justify-between p-2 border rounded">
                <span className="font-medium capitalize">{source}</span>
                <div className="flex items-center space-x-2">
                  <span className={`w-3 h-3 rounded-full ${status.enabled ? 'bg-green-500' : 'bg-gray-400'}`}></span>
                  <span className="text-sm">{status.message}</span>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p>Loading asset source statuses...</p>
        )}
      </div>
    </div>
  );

  const renderValidateTab = () => (
    <div className="space-y-6">
      <div className="bg-white p-6 rounded-lg shadow">
        <h3 className="text-xl font-semibold mb-4">✅ ZW Validation</h3>
        <button
          onClick={handleValidateZW}
          className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 mb-4"
        >
          Validate Current ZW
        </button>
        
        {validationResults && (
          <div className="mt-4">
            <h4 className="font-semibold mb-2">Validation Results:</h4>
            <pre className="bg-gray-100 p-4 rounded overflow-auto text-sm">
              {JSON.stringify(validationResults, null, 2)}
            </pre>
          </div>
        )}
      </div>
    </div>
  );

  const renderExportTab = () => (
    <div className="space-y-6">
      <div className="bg-white p-6 rounded-lg shadow">
        <h3 className="text-xl font-semibold mb-4">📤 Export ZW Content</h3>
        
        <div className="space-y-4">
          <div>
            <h4 className="font-semibold mb-2">Convert to JSON:</h4>
            <button
              onClick={handleConvertToJson}
              className="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700 mb-2"
            >
              🔄 Convert to JSON
            </button>
            {jsonOutput && (
              <textarea
                value={jsonOutput}
                readOnly
                className="w-full px-3 py-2 border rounded-md font-mono text-sm h-32"
              />
            )}
          </div>

          <div>
            <h4 className="font-semibold mb-2">Generate Godot Script:</h4>
            <button
              onClick={handleConvertToGodot}
              className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 mb-2"
            >
              🎮 Generate Godot Script
            </button>
            {godotOutput && (
              <textarea
                value={godotOutput}
                readOnly
                className="w-full px-3 py-2 border rounded-md font-mono text-sm h-32"
              />
            )}
          </div>

          <div>
            <h4 className="font-semibold mb-2">Export Raw ZW:</h4>
            <button
              onClick={() => {
                const blob = new Blob([zwContent], { type: 'text/plain' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = 'zw_content.zw';
                a.click();
                URL.revokeObjectURL(url);
              }}
              disabled={!zwContent.trim()}
              className="px-4 py-2 bg-purple-600 text-white rounded hover:bg-purple-700 disabled:opacity-50"
            >
              💾 Download ZW File
            </button>
          </div>
        </div>
      </div>
    </div>
  );

  const renderVisualizeTab = () => (
    <div className="space-y-6">
      <div className="bg-white p-6 rounded-lg shadow">
        <h3 className="text-xl font-semibold mb-4">👁️ ZW Visualization</h3>
        {zwContent ? (
          <ZWTemplateVisualizer zwContent={zwContent} />
        ) : (
          <p className="text-gray-500">No ZW content to visualize. Create or import content first.</p>
        )}
      </div>
      
      <div className="bg-white p-6 rounded-lg shadow">
        <h3 className="text-xl font-semibold mb-4">🎨 Syntax Highlighting</h3>
        {zwContent ? (
          <ZWSyntaxHighlighter content={zwContent} />
        ) : (
          <p className="text-gray-500">No ZW content to highlight.</p>
        )}
      </div>
    </div>
  );

  const renderProjectsTab = () => (
    <div className="space-y-6">
      <div className="bg-white p-6 rounded-lg shadow">
        <h3 className="text-xl font-semibold mb-4">📁 Project Management</h3>
        <p className="text-gray-600 mb-4">
          Organize your ZW schemas and templates for different game projects.
        </p>
        
        <div className="space-y-4">
          <button className="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700">
            ➕ New Project
          </button>
          
          {projects.length === 0 ? (
            <div className="text-center py-8 text-gray-500">
              <p>No projects yet. Create your first project to get started!</p>
            </div>
          ) : (
            <div className="grid gap-4">
              {projects.map((project, index) => (
                <div key={index} className="border rounded-lg p-4 hover:shadow-md transition-shadow">
                  <h4 className="font-semibold">{project.name}</h4>
                  <p className="text-gray-600 text-sm">{project.description}</p>
                  <div className="mt-2 flex space-x-2">
                    <button className="px-3 py-1 bg-blue-500 text-white rounded text-sm">Open</button>
                    <button className="px-3 py-1 bg-gray-500 text-white rounded text-sm">Edit</button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );

  const renderLibraryTab = () => (
    <div className="space-y-6">
      <div className="bg-white p-6 rounded-lg shadow">
        <h3 className="text-xl font-semibold mb-4">📚 ZW Template Library</h3>
        <p className="text-gray-600 mb-4">
          Pre-built ZW templates for common game development patterns.
        </p>
        
        <div className="grid gap-4">
          <div className="border rounded-lg p-4">
            <h4 className="font-semibold">🎭 Narrative Scene Template</h4>
            <p className="text-gray-600 text-sm">Template for cinematic story beats</p>
            <button 
              onClick={() => setZwContent(`ZW-NARRATIVE-SCENE:
  SCENE_GOAL: "Enter scene goal here"
  EVENT_ID: "CH1_SC01_Example"
  FOCUS: true
  SETTING:
    LOCATION: "Location name"
    TIME_OF_DAY: "Day/Night"
    MOOD: "Emotional tone"
  CHARACTERS_INVOLVED:
    - NAME: "Character name"
      ROLE: "Character role"
      CURRENT_EMOTION: "Current emotion"
  SEQUENCE:
    - TYPE: EVENT
      DESCRIPTION: "What happens"
      ANCHOR: "EventStart"
  META:
    AUTHOR: "ZW Transformer"
    VERSION: "1.0"
    TAGS: ["template"]`)}
              className="mt-2 px-3 py-1 bg-blue-500 text-white rounded text-sm"
            >
              Use Template
            </button>
          </div>
          
          <div className="border rounded-lg p-4">
            <h4 className="font-semibold">🎮 Game Object Template</h4>
            <p className="text-gray-600 text-sm">Template for game objects and items</p>
            <button 
              onClick={() => setZwContent(`ZW-OBJECT:
  NAME: "Object name"
  TYPE: "Object type"
  LOCATION: (0, 0, 0)
  PROPERTIES:
    MATERIAL: "Material name"
    COLOR: "#FFFFFF"
  META:
    AUTHOR: "ZW Transformer"
    VERSION: "1.0"`)}
              className="mt-2 px-3 py-1 bg-blue-500 text-white rounded text-sm"
            >
              Use Template
            </button>
          </div>
        </div>
      </div>
    </div>
  );

  // === MAIN RENDER ===
  return (
    <div className="min-h-screen bg-gray-100">
      {/* Header */}
      <header className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center py-4">
            <div>
              <h1 className="text-2xl font-bold text-gray-900">ZW Transformer</h1>
              <p className="text-sm text-gray-600">AI-Native Game Development Platform</p>
            </div>
            <div className="text-right">
              <div className="text-sm text-gray-500">v0.9.5 • Ollama Integrated</div>
            </div>
          </div>
        </div>
      </header>

      {/* Navigation */}
      <nav className="bg-white border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex space-x-8">
            {[
              { id: 'projects', label: '📁 Projects', },
              { id: 'create', label: '📝 Create' },
              { id: 'validate', label: '✅ Validate' },
              { id: 'visualize', label: '👁️ Visualize' },
              { id: 'export', label: '📤 Export' },
              { id: 'library', label: '📚 Library' },
              { id: 'guide', label: '📖 Guide' }
            ].map(tab => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`py-4 px-1 border-b-2 font-medium text-sm ${
                  activeTab === tab.id
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {activeTab === 'projects' && renderProjectsTab()}
        {activeTab === 'create' && renderCreateTab()}
        {activeTab === 'validate' && renderValidateTab()}
        {activeTab === 'visualize' && renderVisualizeTab()}
        {activeTab === 'export' && renderExportTab()}
        {activeTab === 'library' && renderLibraryTab()}
        {activeTab === 'guide' && renderGuideTab()}
      </main>

      {/* Footer */}
      <footer className="bg-white border-t mt-12">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <div className="text-center text-sm text-gray-500">
            <p>ZW Transformer - Multi-Engine AI Game Development Platform</p>
            <p className="mt-1">Powered by Ollama • Local AI • Zero API Costs</p>
          </div>
        </div>
      </footer>
    </div>
  );
};

// === APP INITIALIZATION ===
const container = document.getElementById('root');
if (container) {
  const root = createRoot(container);
  root.render(<ZWTransformer />);
} else {
  console.error('Root container not found');
}
