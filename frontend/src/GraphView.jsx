import React, { useEffect, useState, useRef } from 'react';
import ForceGraph2D from 'react-force-graph-2d';
import neo4j from 'neo4j-driver';

const URI = import.meta.env.VITE_NEO4J_URI;
const USER = import.meta.env.VITE_NEO4J_USERNAME;
const PWD = import.meta.env.VITE_NEO4J_PASSWORD;

export default function GraphView({ onNodeClick }) {
  const [graphData, setGraphData] = useState({ nodes: [], links: [] });
  const [dimensions, setDimensions] = useState({ width: window.innerWidth, height: window.innerHeight - 80 });
  const fgRef = useRef();

  useEffect(() => {
    const handleResize = () => {
      setDimensions({ width: window.innerWidth, height: window.innerHeight - 80 });
    };
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  useEffect(() => {
    let isMounted = true;
    const driver = neo4j.driver(URI, neo4j.auth.basic(USER, PWD));
    const session = driver.session();

    const query = `
      MATCH (n)-[r]->(m)
      WHERE labels(n)[0] IN ['Section', 'Character', 'Location', 'Fact', 'GlossaryTerm']
        AND labels(m)[0] IN ['Section', 'Character', 'Location', 'Fact', 'GlossaryTerm', 'Insight']
      RETURN n, r, m
      LIMIT 500
    `;

    session.run(query)
      .then(result => {
        if (!isMounted) return;
        const nodes = new Map();
        const links = [];

        result.records.forEach(record => {
          const n = record.get('n');
          const m = record.get('m');
          const r = record.get('r');

          const nId = n.elementId;
          const mId = m.elementId;

          if (!nodes.has(nId)) {
            nodes.set(nId, {
              id: nId,
              label: n.labels[0],
              name: n.properties.title || n.properties.name || n.properties.term || n.properties.topic || n.labels[0],
              val: n.labels[0] === 'Section' ? 20 : 5,
              color: getColor(n.labels[0]),
              ...n.properties
            });
          }
          
          if (!nodes.has(mId)) {
            nodes.set(mId, {
              id: mId,
              label: m.labels[0],
              name: m.properties.title || m.properties.name || m.properties.term || m.properties.topic || m.labels[0],
              val: m.labels[0] === 'Section' ? 20 : 5,
              color: getColor(m.labels[0]),
              ...m.properties
            });
          }

          links.push({
            source: nId,
            target: mId,
            label: r.type
          });
        });

        setGraphData({
          nodes: Array.from(nodes.values()),
          links: links
        });
      })
      .catch(console.error)
      .finally(() => {
        session.close();
        driver.close();
      });

    return () => { isMounted = false; };
  }, []);

  const getColor = (label) => {
    switch(label) {
      case 'Section': return '#94a3b8'; // Slate
      case 'Character': return '#10b981'; // Emerald
      case 'Location': return '#f43f5e'; // Rose
      case 'Fact': return '#3b82f6'; // Blue
      case 'GlossaryTerm': return '#a855f7'; // Purple
      case 'Insight': return '#f97316'; // Orange
      default: return '#cbd5e1';
    }
  };

  return (
    <div className="w-full h-full bg-slate-900 relative">
      <div className="absolute top-4 left-4 z-10 bg-slate-800/80 backdrop-blur-sm p-4 rounded-xl border border-slate-700 text-white shadow-xl">
        <h3 className="font-bold text-lg mb-2">Mahabharata Constellation</h3>
        <ul className="text-xs space-y-1 mb-4">
          <li className="flex items-center gap-2"><span className="w-3 h-3 rounded-full bg-[#94a3b8]"></span> Section</li>
          <li className="flex items-center gap-2"><span className="w-3 h-3 rounded-full bg-[#10b981]"></span> Character</li>
          <li className="flex items-center gap-2"><span className="w-3 h-3 rounded-full bg-[#f43f5e]"></span> Location</li>
          <li className="flex items-center gap-2"><span className="w-3 h-3 rounded-full bg-[#a855f7]"></span> Glossary</li>
          <li className="flex items-center gap-2"><span className="w-3 h-3 rounded-full bg-[#3b82f6]"></span> Lore/Fact</li>
        </ul>
        <p className="text-[10px] text-slate-400">Scroll to zoom. Drag to pan.</p>
        <p className="text-[10px] text-slate-400 mt-1">Click node for details.</p>
      </div>
      
      <ForceGraph2D
        ref={fgRef}
        width={dimensions.width}
        height={dimensions.height}
        graphData={graphData}
        nodeLabel="name"
        nodeColor="color"
        nodeRelSize={6}
        linkColor={() => 'rgba(255,255,255,0.1)'}
        backgroundColor="#0f172a"
        onNodeClick={(node) => {
          fgRef.current.centerAt(node.x, node.y, 1000);
          fgRef.current.zoom(4, 2000);
          if(onNodeClick) onNodeClick(node);
        }}
        nodeCanvasObject={(node, ctx, globalScale) => {
          const label = node.name;
          const fontSize = node.label === 'Section' ? 16/globalScale : 12/globalScale;
          ctx.font = `${fontSize}px Sans-Serif`;
          const textWidth = ctx.measureText(label).width;
          const bckgDimensions = [textWidth, fontSize].map(n => n + fontSize * 0.2); 

          ctx.fillStyle = 'rgba(15, 23, 42, 0.8)';
          ctx.fillRect(node.x - bckgDimensions[0] / 2, node.y - bckgDimensions[1] / 2, ...bckgDimensions);

          ctx.textAlign = 'center';
          ctx.textBaseline = 'middle';
          ctx.fillStyle = node.color;
          ctx.fillText(label, node.x, node.y);

          node.__bckgDimensions = bckgDimensions; 
        }}
        nodePointerAreaPaint={(node, color, ctx) => {
          ctx.fillStyle = color;
          const bckgDimensions = node.__bckgDimensions;
          bckgDimensions && ctx.fillRect(node.x - bckgDimensions[0] / 2, node.y - bckgDimensions[1] / 2, ...bckgDimensions);
        }}
      />
    </div>
  );
}
