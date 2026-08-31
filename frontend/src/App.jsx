import { useEffect, useState } from 'react';
import neo4j from 'neo4j-driver';
import GraphView from './GraphView';
import MiniGraph from './MiniGraph';

const URI = import.meta.env.VITE_NEO4J_URI;
const USER = import.meta.env.VITE_NEO4J_USERNAME;
const PWD = import.meta.env.VITE_NEO4J_PASSWORD;

export default function App() {
  const [currentSection, setCurrentSection] = useState(null);
  const [activeBook, setActiveBook] = useState(null);
  const [sectionData, setSectionData] = useState(null);
  const [indexTree, setIndexTree] = useState({});
  const [bookEpochs, setBookEpochs] = useState({});
  const [expandedParvas, setExpandedParvas] = useState({});
  const [loading, setLoading] = useState(true);
  const [showGraph, setShowGraph] = useState(false);
  
  const [chatQuery, setChatQuery] = useState("");
  const [chatLog, setChatLog] = useState([]);

  // Upload state
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [uploadInput, setUploadInput] = useState("");
  const [uploading, setUploading] = useState(false);
  const [uploadDraft, setUploadDraft] = useState(null);
  const [uploadError, setUploadError] = useState("");
  const [jobStatus, setJobStatus] = useState(null);

  const [selectedItem, setSelectedItem] = useState(null);

  const navigateSection = (direction) => {
    if (!activeBook || !indexTree[activeBook]) return;
    const flatList = Object.values(indexTree[activeBook]).flat();
    const currentIndex = flatList.findIndex(s => s.id === currentSection);
    if (currentIndex === -1) return;
    
    if (direction === 'next' && currentIndex < flatList.length - 1) {
      setCurrentSection(flatList[currentIndex + 1].id);
    } else if (direction === 'prev' && currentIndex > 0) {
      setCurrentSection(flatList[currentIndex - 1].id);
    }
  };

  const renderInteractiveSummary = (text, characters, locations, glossary, lore) => {
    if (!text) return text;
    const terms = [];
    if (glossary) glossary.forEach(g => { if(g.term && g.term.length > 2) terms.push({ word: g.term, type: 'glossary', data: g }); });
    if (lore) lore.forEach(l => { if(l.topic && l.topic.length > 2) terms.push({ word: l.topic, type: 'lore', data: l }); });
    if (characters) characters.forEach(c => { const shortName = c.name.split(' (')[0]; if(shortName && shortName.length > 2) terms.push({ word: shortName, type: 'character', data: c }); });
    if (locations) locations.forEach(l => { if(l.name && l.name.length > 2) terms.push({ word: l.name, type: 'location', data: l }); });

    if (terms.length === 0) return text;

    terms.sort((a, b) => b.word.length - a.word.length);
    const words = terms.map(t => t.word.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'));
    const regex = new RegExp(`\\b(${words.join('|')})\\b`, 'gi');
    
    const parts = text.split(regex);
    
    return parts.map((part, i) => {
      if (!part) return part;
      const matchedTerm = terms.find(t => t.word.toLowerCase() === part.toLowerCase());
      if (matchedTerm && part.trim().length > 0) {
        let colorClass = "text-slate-600 border-slate-300 hover:text-slate-800 hover:bg-slate-50";
        if (matchedTerm.type === 'lore') colorClass = "text-blue-600 border-blue-300 hover:text-blue-800 hover:bg-blue-50";
        if (matchedTerm.type === 'glossary') colorClass = "text-purple-600 border-purple-300 hover:text-purple-800 hover:bg-purple-50";
        if (matchedTerm.type === 'character') colorClass = "text-emerald-600 border-emerald-300 hover:text-emerald-800 hover:bg-emerald-50";
        if (matchedTerm.type === 'location') colorClass = "text-rose-600 border-rose-300 hover:text-rose-800 hover:bg-rose-50";
        
        return (
          <button key={i} onClick={() => setSelectedItem(matchedTerm)} className={`font-semibold border-b-2 border-dotted px-0.5 rounded transition-colors cursor-pointer ${colorClass}`}>
            {part}
          </button>
        );
      }
      return part;
    });
  };

  useEffect(() => {
    let isMounted = true;
    setLoading(true);
    const driver = neo4j.driver(URI, neo4j.auth.basic(USER, PWD));
    const session1 = driver.session();
    
    session1.run(`
      MATCH (b:Book)-[:CONTAINS]->(p:Parva)-[:CONTAINS]->(s:Section)
      RETURN b.title AS book, p.title AS parva, s.global_id AS id, s.title AS title, b.epoch_order AS epoch_order
      ORDER BY s.global_id ASC
    `).then(result1 => {
      if (!isMounted) return;
      const tree = {};
      const epochs = {};
      result1.records.forEach(r => {
        const book = r.get('book');
        const parva = r.get('parva');
        const epoch = r.get('epoch_order');
        if (epoch !== null && epoch !== undefined) {
          epochs[book] = neo4j.isInt(epoch) ? epoch.toNumber() : Number(epoch);
        } else {
          // Fallback legacy sorting
          if (book.includes('Pre-Mahabharata')) epochs[book] = 10;
          else if (book.toLowerCase().includes('book')) {
            const m = book.match(/book\s*(\d+)/i);
            epochs[book] = m ? 50 + parseInt(m[1]) : 60;
          } else if (book.includes('Expanded Universe')) epochs[book] = 999;
          else epochs[book] = 100;
        }
        
        if (!tree[book]) tree[book] = {};
        if (!tree[book][parva]) tree[book][parva] = [];
        tree[book][parva].push({ id: r.get('id'), title: r.get('title') });
      });
      
      setBookEpochs(epochs);
      
      Object.keys(tree).forEach(b => {
        Object.keys(tree[b]).forEach(p => {
          tree[b][p].sort((a, b) => {
             const partsA = a.id.split('_').map(Number);
             const partsB = b.id.split('_').map(Number);
             if (!isNaN(partsA[0]) && !isNaN(partsB[0])) {
               if (partsA[0] !== partsB[0]) return partsA[0] - partsB[0];
               return partsA[1] - partsB[1];
             }
             return a.id.localeCompare(b.id);
          });
        });
      });

      setIndexTree(tree);

      if (!currentSection) {
        setSectionData(null);
        setLoading(false);
        session1.close();
        return;
      }

      let queryParam = currentSection.toString();
      let contentQuery = "";
      
      if (queryParam.startsWith("Parva_")) {
        queryParam = queryParam.replace("Parva_", "");
        contentQuery = `
          MATCH (p:Parva {title: $id})
          RETURN p.title AS title, p.summary AS summary, "" AS url,
                 [] AS characters, [] AS locations, [] AS glossary, [] AS lore, null AS sanskrit_insight, [] AS anchored_sections
        `;
      } else {
        contentQuery = `
          MATCH (s:Section {global_id: $id})
          OPTIONAL MATCH (s)-[rel_char:MENTIONS_CHARACTER]->(char:Character)
          OPTIONAL MATCH (s)-[rel_loc:MENTIONS_LOCATION]->(loc:Location)
          OPTIONAL MATCH (s)-[rel_term:MENTIONS_TERM]->(term:GlossaryTerm)
          OPTIONAL MATCH (s)-[rel_lore:HAS_LORE]->(lore:Fact)
          OPTIONAL MATCH (s)-[rel_sans:HAS_SANSKRIT_INSIGHT]->(sans:Insight)
          OPTIONAL MATCH (s)-[:ANCHORED_TO]-(anchored:Section)
          RETURN s.title AS title, s.summary AS summary, s.url AS url, s.brief_summary AS brief_summary, s.next_part_impact AS next_part_impact,
                 collect(DISTINCT {name: char.name, context: rel_char.context}) AS characters, 
                 collect(DISTINCT {name: loc.name, context: rel_loc.context}) AS locations,
                 collect(DISTINCT {term: term.term, def_in: term.definition_indian, def_intl: term.definition_international, root: term.sanskrit_root, meaning: term.root_meaning}) AS glossary,
                 collect(DISTINCT {topic: lore.topic, fact: lore.content, type: lore.type}) AS lore,
                 collect(DISTINCT {fact: sans.content, verse: sans.sanskrit_verse, translation: sans.translation}) AS sanskrit_insight,
                 collect(DISTINCT {id: anchored.global_id, title: anchored.title}) AS anchored_sections
        `;
      }

      const session2 = driver.session();
      session2.run(contentQuery, { id: queryParam }).then(result2 => {
        if (!isMounted) return;
        
        let foundParva = null;
        let foundBook = null;
        if (currentSection.toString().startsWith("Parva_")) {
           foundParva = currentSection.toString().replace("Parva_", "");
           Object.keys(tree).forEach(b => { if(tree[b][foundParva]) foundBook = b; });
        } else {
           Object.keys(tree).forEach(b => {
             Object.keys(tree[b]).forEach(p => {
               if (tree[b][p].some(s => s.id === currentSection.toString())) { foundParva = p; foundBook = b; }
             });
           });
        }
        if (foundBook) setActiveBook(foundBook);
        if (foundParva) setExpandedParvas(prev => ({ ...prev, [foundParva]: true }));

        if (result2.records.length > 0) {
          const r = result2.records[0];
          setSectionData({
            title: r.get('title'),
            summary: r.get('summary'),
            brief_summary: r.get('brief_summary'),
            next_part_impact: r.get('next_part_impact'),
            url: r.get('url'),
            characters: r.get('characters').filter(c => c && c.name),
            locations: r.get('locations').filter(l => l && l.name),
            glossary: r.get('glossary') ? r.get('glossary').filter(g => g && g.term) : [],
            lore: r.get('lore') ? r.get('lore').filter(l => l && l.topic) : [],
            sanskrit_insight: r.get('sanskrit_insight') ? r.get('sanskrit_insight').filter(s => s && s.fact)[0] : null,
            anchored_sections: r.get('anchored_sections') ? r.get('anchored_sections').filter(a => a && a.id) : []
          });
        } else {
          setSectionData(null);
        }
      }).finally(() => {
        session2.close();
        setLoading(false);
      });
      
    }).catch(err => { console.error(err); setLoading(false); })
    .finally(() => { session1.close(); });

    return () => { isMounted = false; };
  }, [currentSection]);

  const toggleParva = (parva) => { setExpandedParvas(prev => ({ ...prev, [parva]: !prev[parva] })); };

  const handleAskAgent = async (e) => {
    e.preventDefault();
    if (!chatQuery) return;
    const userQ = chatQuery;
    setChatQuery("");
    setChatLog(prev => [...prev, { role: 'user', text: userQ }, { role: 'agent', text: "Graph Agent is thinking..." }]);
    
    try {
      const response = await fetch('http://127.0.0.1:5000/api/ask', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: userQ })
      });
      const data = await response.json();
      setChatLog(prev => { const newLog = [...prev]; newLog[newLog.length - 1] = { role: 'agent', text: data.answer }; return newLog; });
    } catch (error) {
      setChatLog(prev => { const newLog = [...prev]; newLog[newLog.length - 1] = { role: 'agent', text: "Error: backend unreachable." }; return newLog; });
    }
  };

  const pollJobStatus = async (jobId) => {
    try {
      const response = await fetch(`http://127.0.0.1:5000/api/status/${jobId}`);
      if (!response.ok) throw new Error("Job tracking failed");
      const data = await response.json();
      
      if (data.status === 'error') {
        setUploadError(data.message);
        setUploading(false);
        setJobStatus(null);
        return;
      }
      
      setJobStatus({ message: data.message, progress: data.progress });
      
      if (data.status === 'complete') {
        setUploadDraft(data.result);
        setUploading(false);
        setJobStatus(null);
      } else {
        setTimeout(() => pollJobStatus(jobId), 1000);
      }
    } catch (err) {
      setUploadError("Lost connection to job tracker.");
      setUploading(false);
      setJobStatus(null);
    }
  };

  const handleUpload = async () => {
    if (!uploadInput) return;
    setUploading(true);
    setUploadDraft(null);
    setUploadError("");
    setJobStatus(null);
    try {
      const response = await fetch('http://127.0.0.1:5000/api/upload', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ target: uploadInput })
      });
      if (!response.ok) throw new Error("Backend server error.");
      const data = await response.json();
      
      if (data.already_exists) {
         setUploadError(`Duplicate Warning: This exact URL is already mapped to the timeline as "${data.title}".`);
         setUploading(false);
         return;
      }
      if (data.error) throw new Error(data.error);
      
      pollJobStatus(data.job_id);
    } catch (err) {
      setUploadError(err.message || "Failed to connect to backend.");
      setUploading(false);
    }
  };

  const handleBookSelect = (bookName) => {
    setActiveBook(bookName);
    const parvas = indexTree[bookName];
    if (parvas && Object.keys(parvas).length > 0) {
      const firstParva = Object.keys(parvas)[0];
      const firstSection = parvas[firstParva][0];
      setCurrentSection(firstSection.id);
    }
  };

  const jumpToNode = (nodeId) => {
    setCurrentSection(nodeId);
    setShowGraph(false);
  };

  return (
    <div className="flex flex-col h-screen bg-slate-50 font-sans text-slate-800">
      {/* HEADER */}
      <header className="flex-none flex items-center justify-between px-6 py-4 bg-white border-b border-slate-200 shadow-sm z-10">
        <h1 
          className="text-xl font-bold text-indigo-900 flex items-center gap-2 cursor-pointer hover:text-indigo-700"
          onClick={() => { setCurrentSection(null); setActiveBook(null); setShowGraph(false); }}
        >
          <svg className="w-6 h-6 text-indigo-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 10V3L4 14h7v7l9-11h-7z"></path></svg>
          Mythological Multiverse
        </h1>
        <div className="flex gap-3 items-center">
          {currentSection && activeBook && (
            <span className="text-sm font-semibold text-slate-500 mr-2 bg-slate-100 px-3 py-1 rounded-full">
              Reading: {activeBook}
            </span>
          )}
          <button 
            onClick={() => setShowUploadModal(true)}
            className="px-4 py-2 text-sm font-bold rounded-md bg-emerald-600 text-white hover:bg-emerald-700 shadow-sm transition-colors"
          >
            + Add Story
          </button>
          <button 
            onClick={() => setShowGraph(!showGraph)} 
            className={`px-4 py-2 text-sm font-bold rounded-md transition-colors shadow-sm ${showGraph ? 'bg-indigo-100 text-indigo-900 border border-indigo-200' : 'bg-indigo-600 text-white hover:bg-indigo-700'}`}
          >
            {showGraph ? 'Close Graph Universe' : 'View Graph Universe'}
          </button>
          {currentSection && (
            <>
              <div className="w-px bg-slate-300 mx-2 h-6"></div>
              <button onClick={() => navigateSection('prev')} className="px-4 py-2 text-sm font-medium text-slate-600 bg-white border border-slate-300 rounded-md hover:bg-slate-50 transition-colors">&larr; Prev</button>
              <button onClick={() => navigateSection('next')} className="px-4 py-2 text-sm font-medium text-slate-600 bg-white border border-slate-300 rounded-md hover:bg-slate-50 transition-colors shadow-sm">Next &rarr;</button>
            </>
          )}
        </div>
      </header>

      {/* MAIN LAYOUT */}
      {showGraph ? (
        <GraphView onNodeClick={(node) => { if (node.label === 'Section') jumpToNode(node.global_id || node.id); }} />
      ) : currentSection === null ? (
        /* LIBRARY DASHBOARD */
        <div className="flex-1 overflow-y-auto p-12 bg-slate-50">
          <div className="max-w-5xl mx-auto">
            <h2 className="text-4xl font-black text-slate-900 mb-2 font-serif">The Library of Timelines</h2>
            <p className="text-slate-500 text-lg mb-12">Select a linear story to begin exploring the mythological multiverse.</p>
            
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8 relative">
              {/* Optional subtle timeline connector background */}
              <div className="hidden md:block absolute top-1/2 left-0 w-full h-1 bg-slate-200 -z-10 rounded-full transform -translate-y-1/2"></div>
              
              {Object.keys(indexTree).sort((a, b) => {
                return (bookEpochs[a] || 50) - (bookEpochs[b] || 50);
              }).map(book => (
                <div 
                  key={book} 
                  onClick={() => handleBookSelect(book)}
                  className="bg-white rounded-2xl p-6 shadow-sm border border-slate-200 hover:shadow-xl hover:border-indigo-300 transition-all cursor-pointer group flex flex-col h-64"
                >
                  <div className="w-12 h-12 bg-indigo-100 text-indigo-600 rounded-xl flex items-center justify-center mb-4 group-hover:bg-indigo-600 group-hover:text-white transition-colors">
                    <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"></path></svg>
                  </div>
                  <h3 className="text-xl font-bold text-slate-900 mb-2 font-serif group-hover:text-indigo-700">{book}</h3>
                  <p className="text-sm text-slate-500 mb-auto line-clamp-3">
                    Explore the chronological events and characters within this specific storyline. 
                    Connections to other timelines will be visible as interactive crossover nodes.
                  </p>
                  <div className="mt-4 pt-4 border-t border-slate-100 text-xs font-bold text-slate-400 uppercase tracking-wider flex justify-between items-center">
                    <span>{Object.keys(indexTree[book]).length} Chapters</span>
                    <span className="text-indigo-600 opacity-0 group-hover:opacity-100 transition-opacity">Read &rarr;</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      ) : (
        /* READING VIEW */
        <div className="flex flex-1 overflow-hidden">
          
          {/* LEFT: TABLE OF CONTENTS (Filtered by activeBook) */}
          <div className="w-72 bg-white border-r border-slate-200 flex flex-col h-full overflow-hidden shrink-0">
            <div className="p-4 border-b border-slate-100 bg-slate-50">
              <h2 className="font-semibold text-slate-800 font-serif text-lg">{activeBook}</h2>
              <p className="text-xs text-slate-500 mt-1">Linear Timeline</p>
            </div>
            <div className="flex-1 overflow-y-auto p-3 space-y-2">
              {activeBook && indexTree[activeBook] && Object.entries(indexTree[activeBook]).map(([parva, sections]) => (
                <div key={parva} className="mb-1">
                  <button 
                    onClick={() => { toggleParva(parva); setCurrentSection(`Parva_${parva}`); }}
                    className={`flex items-center w-full text-left px-2 py-2 text-sm font-bold rounded transition-colors ${currentSection === `Parva_${parva}` ? 'bg-indigo-100 text-indigo-900' : 'text-slate-700 hover:bg-slate-100'}`}
                  >
                    <span className="w-4 h-4 mr-1 text-slate-400 flex items-center justify-center text-xs">
                      {expandedParvas[parva] ? '▼' : '▶'}
                    </span>
                    {parva}
                  </button>
                  {expandedParvas[parva] && (
                    <div className="ml-4 mt-1 border-l border-slate-200 pl-2 space-y-1">
                      {sections.map((s) => (
                        <button 
                          key={s.id} 
                          onClick={() => setCurrentSection(s.id)}
                          className={`block w-full text-left px-2 py-1.5 text-xs rounded transition-colors ${currentSection === s.id ? 'bg-blue-600 text-white shadow-sm font-medium' : 'text-slate-600 hover:bg-slate-50'}`}
                        >
                          {s.title}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* MIDDLE: READING CANVAS */}
          <div className="flex-1 overflow-y-auto p-8 relative">
            {loading ? (
              <div className="absolute inset-0 flex items-center justify-center bg-slate-50/50 backdrop-blur-sm">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
              </div>
            ) : sectionData ? (
              <div className="max-w-3xl mx-auto space-y-6">
                
                {/* CROSSOVER VISUALIZATION IF ANCHORED */}
                {sectionData.anchored_sections && sectionData.anchored_sections.length > 0 && (
                  <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-200">
                    <h3 className="text-sm font-bold text-slate-800 uppercase tracking-wider mb-4 flex items-center gap-2">
                      <svg className="w-5 h-5 text-indigo-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1"></path></svg>
                      Timeline Crossover Detected
                    </h3>
                    <MiniGraph 
                      currentNode={{ id: currentSection, title: sectionData.title }} 
                      anchoredSections={sectionData.anchored_sections} 
                      onNodeClick={jumpToNode}
                    />
                    <p className="text-xs text-slate-500 mt-3 text-center">Click a connected node to jump to its timeline.</p>
                  </div>
                )}

                <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
                  <div className="p-8">
                    <h2 className="text-3xl font-bold text-slate-900 mb-6 font-serif">
                      {currentSection.toString().startsWith('Parva_') ? `Introduction: ${sectionData.title}` : sectionData.title}
                    </h2>
                    
                    {sectionData.url && (
                      <div className="mb-6 flex items-center gap-2">
                        <span className="text-xs font-bold uppercase tracking-widest text-slate-400">Source:</span>
                        <a href={sectionData.url} target="_blank" rel="noopener noreferrer" className="text-sm font-medium text-blue-600 hover:text-blue-800 underline">
                          {sectionData.url}
                        </a>
                      </div>
                    )}
                    
                    <div className={`mb-8 ${currentSection.toString().startsWith('Parva_') ? '' : 'border-b border-slate-100 pb-8'}`}>
                      
                      {!currentSection.toString().startsWith('Parva_') && sectionData.brief_summary && (
                        <div className="mb-6 p-5 bg-amber-50 rounded-xl border border-amber-100 shadow-sm flex flex-col gap-3">
                          <div>
                            <h4 className="text-[10px] font-bold uppercase tracking-widest text-amber-600 mb-1">In this part...</h4>
                            <p className="text-amber-900 font-medium">{sectionData.brief_summary}</p>
                          </div>
                          <div className="border-t border-amber-200/50 pt-2">
                            <h4 className="text-[10px] font-bold uppercase tracking-widest text-amber-600 mb-1">Impact on next part...</h4>
                            <p className="text-amber-900 italic">{sectionData.next_part_impact}</p>
                          </div>
                        </div>
                      )}

                      <h3 className="text-xs font-bold tracking-wider text-slate-400 uppercase mb-3">
                        {currentSection.toString().startsWith('Parva_') ? 'Book Overview & Foreshadowing' : 'Story Summary'}
                      </h3>
                      <p className="text-slate-700 leading-relaxed whitespace-pre-wrap text-lg">
                        {renderInteractiveSummary(sectionData.summary, sectionData.characters, sectionData.locations, sectionData.glossary, sectionData.lore)}
                      </p>
                      
                      {sectionData.sanskrit_insight && (
                        <div className="mt-8 p-6 bg-orange-50 rounded-xl border border-orange-200 shadow-sm relative overflow-hidden">
                          <div className="absolute top-0 right-0 p-4 opacity-10 text-orange-900 text-6xl font-serif">ॐ</div>
                          <h4 className="text-xs font-bold tracking-widest text-orange-600 uppercase mb-4 flex items-center gap-2">
                            <span className="w-2 h-2 rounded-full bg-orange-400"></span>
                            Original Sanskrit Insight
                          </h4>
                          <p className="text-xl text-orange-900 font-serif mb-2 text-center">{sectionData.sanskrit_insight.verse}</p>
                          <p className="text-sm text-orange-700 italic text-center mb-6">"{sectionData.sanskrit_insight.translation}"</p>
                          
                          <div className="pt-4 border-t border-orange-200">
                            <span className="text-[10px] font-bold uppercase tracking-wider text-orange-500 mb-2 block">Mind-Blowing Fact</span>
                            <p className="text-slate-700 text-sm leading-relaxed">{sectionData.sanskrit_insight.fact}</p>
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            ) : (
               <div className="flex items-center justify-center h-full text-slate-500">Select a section to begin reading.</div>
            )}
          </div>

          {/* RIGHT: AGENT SIDEBAR */}
          <aside className="w-80 bg-white border-l border-slate-200 flex flex-col shrink-0 h-full overflow-hidden">
            <div className="p-4 border-b border-slate-100 bg-slate-50">
              <h3 className="font-bold text-slate-800 flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
                GraphRAG Agent
              </h3>
              <p className="text-xs text-slate-500 mt-1">Cross-reference characters and ask questions about the multiverse.</p>
            </div>
            
            <div className="flex-1 p-5 overflow-y-auto space-y-4">
              {chatLog.map((msg, i) => (
                <div key={i} className={`p-4 rounded-xl text-sm leading-relaxed shadow-sm ${msg.role === 'user' ? 'bg-blue-600 text-white ml-8 rounded-br-sm' : 'bg-slate-100 text-slate-800 mr-8 rounded-bl-sm border border-slate-200'}`}>
                  {msg.text}
                </div>
              ))}
              {chatLog.length === 0 && (
                <div className="text-sm text-slate-400 text-center mt-10 p-6 border border-dashed border-slate-300 rounded-xl">
                  <p className="mb-2 font-semibold">Agent is connected to Neo4j.</p>
                  <p>Try asking: <br/><br/>"Who is Vyasa?" <br/><br/>or<br/><br/> "What are the crossover events?"</p>
                </div>
              )}
            </div>

            <div className="p-4 border-t border-slate-200 bg-slate-50">
              <form onSubmit={handleAskAgent} className="flex gap-2">
                <input 
                  type="text" 
                  value={chatQuery}
                  onChange={(e) => setChatQuery(e.target.value)}
                  placeholder="Ask the Agent..." 
                  className="flex-1 px-4 py-3 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 shadow-sm"
                />
                <button type="submit" className="px-5 py-3 bg-slate-800 text-white rounded-lg text-sm font-bold hover:bg-slate-700 shadow-sm transition">
                  Send
                </button>
              </form>
            </div>
          </aside>
        </div>
      )}

      {/* UNIFIED INTERACTIVE MODAL */}
      {selectedItem && (
        <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-sm z-50 flex items-center justify-center p-4" onClick={() => setSelectedItem(null)}>
          <div className="bg-white rounded-2xl shadow-2xl max-w-lg w-full overflow-hidden" onClick={e => e.stopPropagation()}>
            <div className="p-6">
              <div className="flex justify-between items-start mb-4">
                <h3 className="text-2xl font-bold text-slate-900">{selectedItem.word}</h3>
                <button onClick={() => setSelectedItem(null)} className="text-slate-400 hover:text-slate-600 bg-slate-100 rounded-full w-8 h-8 flex items-center justify-center">×</button>
              </div>
              
              {selectedItem.type === 'lore' ? (
                <>
                  <div className="inline-flex items-center gap-2 mb-4">
                    <span className="px-2.5 py-1 rounded-full text-[10px] font-bold uppercase tracking-wider bg-blue-100 text-blue-700">
                      {selectedItem.data.type || 'Mind-Blowing Fact'}
                    </span>
                  </div>
                  <p className="text-slate-700 text-lg leading-relaxed">{selectedItem.data.fact}</p>
                </>
              ) : selectedItem.type === 'character' ? (
                <>
                  <div className="inline-flex items-center gap-2 mb-4">
                    <span className="px-2.5 py-1 rounded-full text-[10px] font-bold uppercase tracking-wider bg-emerald-100 text-emerald-700">Character</span>
                  </div>
                  <p className="text-slate-700 text-lg leading-relaxed">{selectedItem.data.context || selectedItem.data.name}</p>
                </>
              ) : selectedItem.type === 'location' ? (
                <>
                  <div className="inline-flex items-center gap-2 mb-4">
                    <span className="px-2.5 py-1 rounded-full text-[10px] font-bold uppercase tracking-wider bg-rose-100 text-rose-700">Location</span>
                  </div>
                  <p className="text-slate-700 text-lg leading-relaxed">{selectedItem.data.context || selectedItem.data.name}</p>
                </>
              ) : (
                <>
                  <div className="inline-flex items-center gap-2 mb-4">
                    <span className="px-2.5 py-1 rounded-full text-[10px] font-bold uppercase tracking-wider bg-purple-100 text-purple-700">Glossary Term</span>
                  </div>
                  {selectedItem.data.root && (
                    <div className="mb-4 p-3 bg-purple-50 rounded-lg border border-purple-100">
                      <h4 className="text-[10px] font-bold uppercase tracking-widest text-purple-500 mb-1">Sanskrit Etymology</h4>
                      <p className="text-purple-900 font-serif font-medium text-lg">{selectedItem.data.root} <span className="text-sm text-purple-700 font-sans italic">({selectedItem.data.meaning})</span></p>
                    </div>
                  )}
                  <div className="mb-4">
                    <h4 className="text-[10px] font-bold uppercase tracking-widest text-purple-400 mb-1">Indian Context</h4>
                    <p className="text-slate-700">{selectedItem.data.def_in}</p>
                  </div>
                  <div>
                    <h4 className="text-[10px] font-bold uppercase tracking-widest text-purple-400 mb-1">International Context</h4>
                    <p className="text-slate-700">{selectedItem.data.def_intl}</p>
                  </div>
                </>
              )}
            </div>
          </div>
        </div>
      )}

      {/* UPLOAD MODAL */}
      {showUploadModal && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-2xl max-w-2xl w-full flex flex-col max-h-[90vh]">
            <div className="p-6 border-b border-slate-200 flex justify-between items-center">
              <h3 className="text-2xl font-bold text-slate-900">Add to Universe</h3>
              <button onClick={() => { setShowUploadModal(false); setUploadDraft(null); }} className="text-slate-400 hover:text-slate-600 bg-slate-100 rounded-full w-8 h-8 flex items-center justify-center">×</button>
            </div>
            
            <div className="p-6 overflow-y-auto">
              {!uploadDraft && !jobStatus ? (
                <>
                  <p className="text-slate-600 mb-4">Paste a URL, an absolute path to a PDF, or raw text to expand the mythological universe.</p>
                  <textarea 
                    value={uploadInput}
                    onChange={e => setUploadInput(e.target.value)}
                    placeholder="https://en.wikipedia.org/wiki/Matsya..."
                    className="w-full h-32 p-4 border border-slate-300 rounded-xl focus:ring-2 focus:ring-emerald-500 focus:outline-none mb-4 font-mono text-sm"
                  />
                  <button 
                    onClick={handleUpload}
                    disabled={uploading || !uploadInput}
                    className="w-full py-4 bg-emerald-600 text-white font-bold rounded-xl hover:bg-emerald-700 disabled:bg-slate-300 transition-colors"
                  >
                    {uploading ? "Starting Job..." : "Analyze & Classify"}
                  </button>
                  {uploadError && (
                    <div className="mt-4 p-4 bg-red-50 border border-red-200 text-red-700 rounded-xl text-sm font-semibold">
                      {uploadError}
                    </div>
                  )}
                </>
              ) : jobStatus ? (
                <div className="flex flex-col items-center justify-center p-12 text-center gap-6">
                  <h4 className="text-xl font-bold text-slate-800">{jobStatus.message}</h4>
                  <div className="w-full bg-slate-200 rounded-full h-4">
                    <div className="bg-emerald-500 h-4 rounded-full transition-all duration-500" style={{ width: `${jobStatus.progress}%` }}></div>
                  </div>
                  <p className="text-slate-500 font-mono text-sm">{jobStatus.progress}% Complete</p>
                </div>
              ) : (
                <div className="flex flex-col gap-6">
                  <div className="p-4 bg-blue-50 border border-blue-200 rounded-xl">
                    <h4 className="text-sm font-bold text-blue-800 uppercase tracking-wider mb-2">AI Classification Complete</h4>
                    <p className="text-blue-900">This upload was automatically split into <strong>{uploadDraft.length}</strong> chunk(s).</p>
                  </div>
                  
                  <div className="flex flex-col gap-4 max-h-96 overflow-y-auto pr-2">
                    {uploadDraft.map((draft, idx) => (
                      <div key={idx} className="border border-slate-200 rounded-xl p-5 bg-slate-50 shadow-sm">
                        <div className="flex justify-between items-center mb-3">
                          <h4 className="font-bold text-slate-900">Part {draft.part_number} of {draft.total_parts}</h4>
                          <span className="text-xs text-blue-800 font-bold bg-blue-100 px-3 py-1 rounded-full">
                             {draft.dynamic_classification?.book_title} &rarr; {draft.dynamic_classification?.parva_title}
                          </span>
                        </div>
                        <p className="text-sm text-slate-700 leading-relaxed bg-white p-4 rounded-lg border border-slate-200">{draft.summary}</p>
                      </div>
                    ))}
                  </div>
                  
                  <div className="flex gap-4 pt-4 border-t border-slate-200 flex-col">
                    {uploadError && (
                      <div className="p-4 bg-red-50 border border-red-200 text-red-700 rounded-xl text-sm font-semibold">{uploadError}</div>
                    )}
                    <div className="flex gap-4 w-full">
                      <button 
                        onClick={async () => {
                          setUploading(true);
                          setUploadError("");
                          try {
                            const response = await fetch('http://127.0.0.1:5000/api/approve', {
                              method: 'POST',
                              headers: { 'Content-Type': 'application/json' },
                              body: JSON.stringify(uploadDraft)
                            });
                            if (!response.ok) throw new Error("Backend server error.");
                            const data = await response.json();
                            if (data.error) throw new Error(data.error);
                            
                            setShowUploadModal(false);
                            window.location.reload(); 
                          } catch (err) {
                            setUploadError(err.message || "Failed to save to database.");
                          }
                          setUploading(false);
                        }} 
                        className="flex-1 py-3 bg-emerald-600 text-white font-bold rounded-xl hover:bg-emerald-700 transition"
                        disabled={uploading}
                      >
                        {uploading ? "Saving to Neo4j..." : `Approve All ${uploadDraft.length} Parts`}
                      </button>
                      <button onClick={() => setUploadDraft(null)} className="flex-1 py-3 bg-white text-slate-600 border border-slate-300 font-bold rounded-xl hover:bg-slate-50 transition" disabled={uploading}>Reject</button>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
