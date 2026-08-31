import React, { useRef, useEffect, useState } from 'react';
import ForceGraph2D from 'react-force-graph-2d';

export default function MiniGraph({ currentNode, anchoredSections, onNodeClick }) {
  const fgRef = useRef();
  const [dimensions, setDimensions] = useState({ width: 600, height: 300 });
  const containerRef = useRef();

  useEffect(() => {
    if (containerRef.current) {
      setDimensions({
        width: containerRef.current.offsetWidth,
        height: 300
      });
    }
    
    const handleResize = () => {
      if (containerRef.current) {
        setDimensions({
          width: containerRef.current.offsetWidth,
          height: 300
        });
      }
    };
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  const nodes = [
    { id: currentNode.id, name: currentNode.title, val: 20, color: '#f43f5e', label: 'Current' }
  ];
  
  const links = [];

  anchoredSections.forEach(section => {
    nodes.push({ id: section.id, name: section.title, val: 15, color: '#94a3b8', label: 'Section' });
    links.push({ source: currentNode.id, target: section.id, label: 'CROSSOVER' });
  });

  const graphData = { nodes, links };

  return (
    <div ref={containerRef} className="w-full bg-slate-900 rounded-xl overflow-hidden border border-slate-700 relative">
      <div className="absolute top-2 left-3 z-10 text-white text-xs opacity-70">
        Interactive Timeline Crossover
      </div>
      <ForceGraph2D
        ref={fgRef}
        width={dimensions.width}
        height={dimensions.height}
        graphData={graphData}
        nodeLabel="name"
        nodeColor="color"
        nodeRelSize={6}
        linkColor={() => 'rgba(255,255,255,0.3)'}
        backgroundColor="#0f172a"
        onNodeClick={(node) => {
          if (node.id !== currentNode.id && onNodeClick) {
            onNodeClick(node.id);
          }
        }}
        nodeCanvasObject={(node, ctx, globalScale) => {
          const label = node.name;
          const fontSize = 12/globalScale;
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
