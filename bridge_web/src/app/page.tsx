"use client";

import { useEffect, useState, useRef } from "react";
import { Play, Square, Activity, Bot, Code, MonitorPlay, Loader2, Eraser, AlertOctagon, Send, ChevronDown } from "lucide-react";

type LogEvent = {
  id: number;
  message: string;
};

type AgentState = "idle" | "running" | "stopping";

export default function Dashboard() {
  const [antigravityLogs, setAntigravityLogs] = useState<LogEvent[]>([]);
  const [claudeLogs, setClaudeLogs] = useState<LogEvent[]>([]);
  const [chatgptLogs, setChatgptLogs] = useState<LogEvent[]>([]);
  const [systemLogs, setSystemLogs] = useState<LogEvent[]>([]);
  
  const [isConnected, setIsConnected] = useState(false);
  const [activePrompt, setActivePrompt] = useState<string | null>(null);
  const [promptResponse, setPromptResponse] = useState("");
  const [initialTask, setInitialTask] = useState("");
  const [agentState, setAgentState] = useState<AgentState>("idle");
  const [activePanel, setActivePanel] = useState<string | null>(null);
  const [hasStarted, setHasStarted] = useState(false);
  
  const [models, setModels] = useState<string[]>([]);
  const [activeModel, setActiveModel] = useState<string>("");
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  
  const wsRef = useRef<WebSocket | null>(null);
  
  const scrollRefs = {
    antigravity: useRef<HTMLDivElement>(null),
    claude: useRef<HTMLDivElement>(null),
    chatgpt: useRef<HTMLDivElement>(null),
    system: useRef<HTMLDivElement>(null),
  };
  
  const logIdCounter = useRef(0);

  // Fetch Models
  useEffect(() => {
    fetch("http://localhost:8000/api/models")
      .then(res => res.json())
      .then(data => {
        if (data.models && data.models.length > 0) {
          setModels(data.models);
        } else {
          setModels(["No Models Found"]);
        }
        if (data.active) setActiveModel(data.active);
      })
      .catch(err => {
        console.error("Fetch models failed:", err);
        setModels(["API Offline"]);
      });
  }, []);

  useEffect(() => {
    let reconnectTimer: NodeJS.Timeout;
    
    const connect = () => {
      const ws = new WebSocket("ws://localhost:8000/ws/stream");
      
      ws.onopen = () => setIsConnected(true);
      
      ws.onclose = () => {
        setIsConnected(false);
        reconnectTimer = setTimeout(connect, 2000);
      };
      
      ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.type === "log") {
          const msg = data.data.message;
          const logObj = { id: logIdCounter.current++, message: msg };
          
          if (msg.includes("[System] Agent gracefully stopped.")) {
            setAgentState("idle");
          }
  
          // Log Routing Logic
          if (msg.includes("[Antigravity]")) {
            setAntigravityLogs(prev => [...prev, logObj]);
            setActivePanel("antigravity");
          } else if (msg.includes("[Critic]") || msg.toLowerCase().includes("chatgpt")) {
            setChatgptLogs(prev => [...prev, logObj]);
            setActivePanel("chatgpt");
          } else if (msg.includes("Chat UI") || msg.includes("Phase 1:") || msg.toLowerCase().includes("claude") || msg.includes("[Orchestrator]")) {
            setClaudeLogs(prev => [...prev, logObj]);
            setActivePanel("claude");
          } else {
            setSystemLogs(prev => [...prev, logObj]);
            setActivePanel("system");
          }
        } else if (data.type === "input_required") {
          setActivePrompt(data.data.prompt);
        }
      };
      
      wsRef.current = ws;
    };

    connect();
    
    return () => {
      clearTimeout(reconnectTimer);
      if (wsRef.current) wsRef.current.close();
    };
  }, []);

  // Auto-scroll effect for vertical logs
  useEffect(() => {
    Object.values(scrollRefs).forEach(ref => {
      if (ref.current) {
        ref.current.scrollTop = ref.current.scrollHeight;
      }
    });
  }, [antigravityLogs, claudeLogs, chatgptLogs, systemLogs, activePrompt]);

  // Auto-center horizontal slider to active panel
  useEffect(() => {
    if (activePanel) {
      const container = document.getElementById("panels-container");
      const el = document.getElementById(`panel-${activePanel}`);
      if (container && el) {
        const scrollLeft = el.offsetLeft - container.offsetWidth / 2 + el.offsetWidth / 2;
        container.scrollTo({ left: scrollLeft, behavior: "smooth" });
      }
    }
  }, [activePanel]);

  const clearLogs = () => {
    setAntigravityLogs([]);
    setClaudeLogs([]);
    setChatgptLogs([]);
    setSystemLogs([]);
    setActivePanel(null);
    setHasStarted(false);
  };

  const handleStart = async () => {
    if (!initialTask) return;
    setAgentState("running");
    setHasStarted(true);
    try {
      const res = await fetch("http://localhost:8000/api/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ task: initialTask })
      });
      if (res.ok) {
        setSystemLogs(prev => [...prev, { id: logIdCounter.current++, message: "[System] Bridge Engine Started in Background..." }]);
      }
    } catch (error) {
      console.error(error);
      setAgentState("idle");
    }
  };

  const handleStop = async () => {
    setAgentState("stopping");
    try {
      await fetch("http://localhost:8000/api/stop", { method: "POST" });
      setSystemLogs(prev => [...prev, { id: logIdCounter.current++, message: "[System] Stop signal sent. Waiting for agent to halt..." }]);
      
      setTimeout(() => {
        setAgentState(prev => {
          if (prev === "stopping") {
            setSystemLogs(logs => [...logs, { id: logIdCounter.current++, message: "[System] Agent stopped (timeout fallback)." }]);
            return "idle";
          }
          return prev;
        });
      }, 5000);
    } catch (error) {
      console.warn("Failed to reach backend:", error);
      setAgentState("idle");
    }
  };

  const handleModelChange = async (newModel: string) => {
    setActiveModel(newModel);
    try {
      await fetch("http://localhost:8000/api/models/active", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ model_name: newModel })
      });
    } catch (err) {
      console.error(err);
    }
  };

  const handlePromptSubmit = () => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: "input_response", value: promptResponse }));
      setActivePrompt(null);
      setPromptResponse("");
    }
  };

  const LogPanel = ({ title, icon: Icon, logs, scrollRefKey, panelKey }: any) => {
    const isActive = activePanel === panelKey;
    return (
      <div id={`panel-${panelKey}`} className={`shrink-0 w-[85vw] sm:w-[480px] h-[340px] flex flex-col rounded-2xl overflow-hidden transition-all duration-300 snap-center shadow-2xl ${
        isActive 
          ? 'ring-2 ring-[#E9D9B9]/60 bg-[#2C2B29] scale-[1.02]' 
          : 'bg-[#2A2927] hover:bg-[#2C2B29] border border-[#3A3937] scale-100 opacity-90 hover:opacity-100'
      }`}>
        <div className="flex items-center gap-3 px-5 py-3 border-b border-[#3A3937]/50 bg-[#242321]/30">
          <Icon size={16} className={isActive ? 'text-[#E9D9B9]' : 'text-[#8A8987]'} />
          <span className={`text-xs font-semibold uppercase tracking-wider ${isActive ? 'text-[#E9D9B9]' : 'text-[#8A8987]'}`}>{title}</span>
          {isActive && <span className="w-1.5 h-1.5 rounded-full bg-[#E9D9B9] animate-pulse ml-auto shadow-[0_0_8px_rgba(233,217,185,0.8)]" />}
        </div>
        <div className="flex-1 p-5 font-mono text-[13px] leading-relaxed overflow-y-auto" ref={scrollRefs[scrollRefKey as keyof typeof scrollRefs]}>
          {logs.length === 0 ? (
            <div className="text-[#6A6967] mt-2 italic flex items-center justify-center h-full opacity-50">Waiting for logs...</div>
          ) : (
            logs.map((log: LogEvent) => (
              <div 
                key={log.id}
                className={`mb-3 break-words ${
                  log.message.includes('Error') || log.message.includes('Exception') || log.message.includes('fail') 
                    ? 'text-[#DA8769] font-medium' 
                    : 'text-[#C5BDB0]'
                }`}
              >
                {log.message}
              </div>
            ))
          )}
        </div>
      </div>
    );
  };

  return (
    <div className="h-screen w-screen overflow-hidden bg-[#242321] text-[#E6DED0] font-sans flex flex-col selection:bg-[#E9D9B9] selection:text-[#242321]">
      {/* Main Content Area */}
      <div className={`flex-1 flex flex-col items-center px-4 w-full max-w-4xl mx-auto min-h-0 overflow-y-auto hide-scrollbar transition-all duration-700 ease-in-out ${
        hasStarted ? "justify-start pt-[8vh] pb-8" : "justify-center"
      }`}>
        
        {/* Title (Collapses when running) */}
        <div className={`flex items-center gap-3 transition-all duration-700 ease-in-out overflow-hidden cursor-default ${
          hasStarted ? "h-0 opacity-0 mb-0 scale-95 pointer-events-none mt-0" : "h-[40px] opacity-100 mb-8 mt-4 scale-100"
        }`}>
          <div className="text-[#DA8769] flex items-center justify-center">
            {/* Custom Sunburst SVG */}
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" className="animate-[spin_20s_linear_infinite]">
              <path d="M12 2v20M4.93 4.93l14.14 14.14M2 12h20M4.93 19.07L19.07 4.93" />
            </svg>
          </div>
          <h1 className="text-3xl md:text-4xl tracking-tight" style={{ fontFamily: 'Georgia, "Times New Roman", serif' }}>Antigravity Bridge</h1>
        </div>

        {/* Input Container */}
        <div className={`w-full bg-[#2A2927]/90 backdrop-blur-md shadow-2xl border transition-all duration-700 focus-within:border-[#6A6967] ${
          hasStarted ? "rounded-2xl p-2 border-[#3A3937]/50 max-w-3xl" : "rounded-[2rem] p-3 border-[#3A3937] hover:border-[#4A4947]"
        }`}>
          <div className="flex items-center gap-3 px-3 py-2">
            <span className="text-[#8A8987] ml-2 text-2xl font-light cursor-pointer hover:text-[#E6DED0] transition-colors">+</span>
            <input 
              value={initialTask}
              onChange={(e) => setInitialTask(e.target.value)}
              placeholder="How can I help you today?"
              className="flex-1 bg-transparent border-none focus:outline-none text-[1.1rem] text-[#E6DED0] placeholder-[#6A6967] h-12 ml-2"
              disabled={agentState !== "idle"}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && initialTask && agentState === 'idle') {
                  handleStart();
                }
              }}
            />
            {/* Custom Model Dropdown */}
            <div className="relative mr-2">
              <div 
                onClick={() => agentState === 'idle' && setIsDropdownOpen(!isDropdownOpen)}
                className={`flex items-center gap-2 px-3 py-1.5 rounded-lg transition-colors cursor-pointer border border-[#4A4947] ${
                  agentState !== 'idle' ? 'opacity-50 cursor-not-allowed bg-[#3A3937]/20' : 'bg-[#3A3937]/40 hover:bg-[#3A3937]/80'
                }`}
              >
                <span className="text-xs text-[#D6CEBF] font-medium min-w-[80px] text-right">
                  {models.length === 0 ? "Loading..." : activeModel}
                </span>
                <ChevronDown size={14} className="text-[#A6A095]" />
              </div>
              
              {isDropdownOpen && models.length > 0 && agentState === 'idle' && (
                <>
                  <div className="fixed inset-0 z-40" onClick={() => setIsDropdownOpen(false)} />
                  <div className="absolute top-full mt-2 right-0 bg-[#2A2927] border border-[#4A4947] rounded-xl shadow-[0_8px_30px_rgb(0,0,0,0.5)] py-1.5 z-50 min-w-[160px] animate-in fade-in zoom-in-95 duration-100">
                    {models.map(m => (
                      <div 
                        key={m} 
                        onClick={() => {
                          handleModelChange(m);
                          setIsDropdownOpen(false);
                        }}
                        className={`px-4 py-2.5 text-sm cursor-pointer transition-colors mx-1.5 rounded-md ${
                          activeModel === m 
                            ? 'bg-[#3A3937] text-[#E9D9B9] font-medium' 
                            : 'text-[#C5BDB0] hover:bg-[#3A3937]/60 hover:text-white'
                        }`}
                      >
                        {m}
                      </div>
                    ))}
                  </div>
                </>
              )}
            </div>

            {/* Send Button */}
            <button 
              onClick={handleStart}
              disabled={!initialTask || agentState !== 'idle'}
              className="flex items-center justify-center w-10 h-10 rounded-xl bg-[#E9D9B9] text-[#242321] hover:bg-white disabled:opacity-50 disabled:bg-[#3A3937] disabled:text-[#8A8987] transition-colors ml-1"
            >
              <Send size={18} className={initialTask && agentState === 'idle' ? 'ml-0.5' : ''} />
            </button>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex flex-wrap items-center justify-center gap-3 mt-8 pb-4">
          {agentState === "idle" ? (
            <button onClick={handleStart} className="flex items-center gap-2 px-5 py-2.5 bg-[#363533] hover:bg-[#464543] rounded-full text-sm font-medium transition-colors border border-[#4A4947] shadow-sm">
              <Play size={14} className="text-[#A6A095]" /> Start Agent
            </button>
          ) : agentState === "running" ? (
            <button onClick={handleStop} className="flex items-center gap-2 px-5 py-2.5 bg-[#DA8769]/10 hover:bg-[#DA8769]/20 text-[#DA8769] rounded-full text-sm font-medium transition-colors border border-[#DA8769]/30 shadow-sm">
              <Square size={14} className="fill-current" /> Stop Agent
            </button>
          ) : (
            <button disabled className="flex items-center gap-2 px-5 py-2.5 bg-[#363533] rounded-full text-sm font-medium opacity-50 border border-[#4A4947]">
              <Loader2 size={14} className="animate-spin" /> Stopping...
            </button>
          )}

          <button onClick={clearLogs} className="flex items-center gap-2 px-5 py-2.5 bg-[#363533] hover:bg-[#464543] rounded-full text-sm font-medium transition-colors border border-[#4A4947] shadow-sm">
            <Eraser size={14} className="text-[#A6A095]" /> Clear Logs
          </button>

          {agentState !== "idle" && (
            <button onClick={handleStop} className="flex items-center gap-2 px-5 py-2.5 bg-[#363533] hover:bg-red-950/40 hover:text-red-400 rounded-full text-sm font-medium transition-colors border border-[#4A4947] shadow-sm text-[#A6A095]">
              <AlertOctagon size={14} /> Force Stop
            </button>
          )}

          <div className="ml-4 flex items-center gap-2 text-xs font-medium text-[#6A6967] uppercase tracking-widest px-4 py-2 rounded-full border border-[#3A3937]">
            <div className={`w-1.5 h-1.5 rounded-full ${isConnected ? 'bg-emerald-500/80 shadow-[0_0_6px_rgba(16,185,129,0.5)]' : 'bg-red-500/80'}`} />
            {isConnected ? 'Live' : 'Offline'}
          </div>
        </div>

        {/* Active Prompt Response Input */}
        {activePrompt && (
          <div className="mt-8 w-full max-w-2xl bg-[#E9D9B9]/5 border border-[#E9D9B9]/20 rounded-2xl p-5 flex flex-col gap-4 shadow-xl backdrop-blur-sm animate-in fade-in slide-in-from-bottom-4">
            <div className="flex items-center gap-3">
              <span className="w-2 h-2 rounded-full bg-[#E9D9B9] animate-pulse shadow-[0_0_8px_rgba(233,217,185,0.6)]" />
              <span className="text-sm font-medium text-[#E9D9B9]">{activePrompt}</span>
            </div>
            <div className="flex gap-2">
              {activePrompt.toLowerCase().includes("(y/n)") ? (
                <>
                  <button onClick={() => { 
                    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
                      wsRef.current.send(JSON.stringify({ type: "input_response", value: "y" }));
                      setActivePrompt(null);
                    }
                  }} className="bg-[#E9D9B9] text-[#242321] hover:bg-white px-8 py-2.5 rounded-xl text-sm font-semibold transition-colors">Yes</button>
                  <button onClick={() => { 
                    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
                      wsRef.current.send(JSON.stringify({ type: "input_response", value: "n" }));
                      setActivePrompt(null);
                    }
                  }} className="border border-[#E9D9B9]/40 text-[#E9D9B9] hover:bg-[#E9D9B9]/10 px-8 py-2.5 rounded-xl text-sm font-semibold transition-colors">No</button>
                </>
              ) : (
                <>
                  <input 
                    value={promptResponse}
                    onChange={(e) => setPromptResponse(e.target.value)}
                    placeholder="Type response..."
                    className="flex-1 bg-[#2A2927] border border-[#4A4947] focus:border-[#E9D9B9]/60 outline-none text-[#E6DED0] px-4 rounded-xl text-sm transition-colors"
                    onKeyDown={(e) => e.key === 'Enter' && handlePromptSubmit()}
                    autoFocus
                  />
                  <button onClick={handlePromptSubmit} className="bg-[#E9D9B9] text-[#242321] hover:bg-white px-8 py-2.5 rounded-xl text-sm font-semibold transition-colors">
                    Send
                  </button>
                </>
              )}
            </div>
          </div>
        )}

      </div>

      {/* Horizontal Slideshow Logs */}
      <div id="panels-container" className={`w-full overflow-x-auto px-6 sm:px-12 snap-x snap-mandatory hide-scrollbar shrink-0 transition-all duration-700 ease-in-out ${
        hasStarted ? "opacity-100 pb-12 pt-6 translate-y-0 h-auto max-h-[500px]" : "opacity-0 translate-y-10 h-0 overflow-hidden pointer-events-none"
      }`}>
        <div className="flex gap-6 min-w-max">
          {/* Invisible spacer for padding start */}
          <div className="w-[calc(50vw-250px)] shrink-0" />
          
          <LogPanel title="Antigravity (Local Builder)" icon={Code} logs={antigravityLogs} scrollRefKey="antigravity" panelKey="antigravity" />
          <LogPanel title="Claude (Architect)" icon={Bot} logs={claudeLogs} scrollRefKey="claude" panelKey="claude" />
          <LogPanel title="ChatGPT (Critic)" icon={Activity} logs={chatgptLogs} scrollRefKey="chatgpt" panelKey="chatgpt" />
          <LogPanel title="Webpage Inspector & System" icon={MonitorPlay} logs={systemLogs} scrollRefKey="system" panelKey="system" />
          
          {/* Invisible spacer for padding end */}
          <div className="w-[calc(50vw-250px)] shrink-0" />
        </div>
      </div>
      
      {/* Hide Scrollbar Style */}
      <style dangerouslySetInnerHTML={{__html: `
        .hide-scrollbar::-webkit-scrollbar {
          display: none;
        }
        .hide-scrollbar {
          -ms-overflow-style: none;
          scrollbar-width: none;
        }
      `}} />
    </div>
  );
}
