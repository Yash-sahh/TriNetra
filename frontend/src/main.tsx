import React, { useEffect, useMemo, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import CytoscapeComponent from 'react-cytoscapejs';
import {
  AlertTriangle,
  BarChart3,
  Bot,
  Clock,
  FileText,
  FolderOpen,
  GitFork,
  HelpCircle,
  History,
  Info,
  LayoutDashboard,
  LogOut,
  Network,
  Plus,
  RefreshCw,
  Search,
  Shield,
  ShieldCheck,
  Upload,
  Users,
  ZoomIn,
  ZoomOut,
  Maximize2
} from 'lucide-react';
import './styles.css';

const API = import.meta.env.VITE_API_URL || '/api';
type Item = Record<string, any>;

const DEMO_ACCOUNTS = [
  { name: 'Asha Admin', role: 'ADMIN', email: 'admin@example.com' },
  { name: 'Dev Supervisor', role: 'SUPERVISOR', email: 'supervisor@example.com' },
  { name: 'Ira Investigator', role: 'INVESTIGATOR', email: 'investigator@example.com' },
  { name: 'Anil Analyst', role: 'ANALYST', email: 'analyst@example.com' },
  { name: 'Vik Viewer', role: 'VIEWER', email: 'viewer@example.com' },
];

async function api(path: string, token?: string, opts: RequestInit = {}) {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(opts.headers as Record<string, string> || {}),
  };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  const r = await fetch(API + path, { ...opts, headers });
  if (r.status === 401) {
    window.dispatchEvent(new CustomEvent('trinetra-unauthorized'));
    throw new Error('Session expired or unauthorized. Please sign in again.');
  }
  if (!r.ok) {
    const err = await r.json().catch(() => ({ detail: 'Request failed' }));
    throw new Error(err.detail || 'Request failed');
  }
  const contentType = r.headers.get('content-type') || '';
  if (contentType.includes('application/json')) {
    return r.json();
  }
  return r.text();
}

const typeColors: Record<string, string> = {
  Person: '#3b82f6',
  Phone: '#a855f7',
  Vehicle: '#f59e0b',
  BankAccount: '#22c55e',
  Location: '#06b6d4',
  Organization: '#ec4899',
  CrimeEvent: '#ef4444',
  Document: '#64748b',
};

function Badge({ children, kind = 'neutral' }: { children: any; kind?: string }) {
  return <span className={'badge ' + kind}>{children}</span>;
}

function Notice() {
  return (
    <div className="notice" role="note">
      <ShieldCheck size={16} />
      <span>AI assists investigators; it provides analytical leads and does not establish guilt or final legal conclusions.</span>
    </div>
  );
}

function Stat({ label, value, sub }: { label: string; value: any; sub: string }) {
  return (
    <div className="stat">
      <small>{label}</small>
      <strong>{value}</strong>
      <span>{sub}</span>
    </div>
  );
}

// -------------------------------------------------------------
// LOGIN COMPONENT
// -------------------------------------------------------------
function Login({ onLogin }: { onLogin: (x: any) => void }) {
  const [email, setEmail] = useState('admin@example.com');
  const [password, setPassword] = useState('TriNetraDemo!2026');
  const [err, setErr] = useState('');
  const [busy, setBusy] = useState(false);

  const submit = async (e?: React.FormEvent) => {
    e?.preventDefault();
    if (DEMO_ACCOUNTS.some((acc) => acc.email === email)) {
      await enterDemo(email);
      return;
    }
    setBusy(true);
    setErr('');
    try {
      const res = await api('/auth/login', undefined, {
        method: 'POST',
        body: JSON.stringify({ email, password }),
      });
      onLogin(res);
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  };

  const enterDemo = async (demoEmail: string) => {
    setBusy(true);
    setErr('');
    try {
      const res = await api('/auth/demo-login', undefined, {
        method: 'POST',
        body: JSON.stringify({ email: demoEmail }),
      });
      onLogin(res);
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  };

  const pickDemo = (acc: (typeof DEMO_ACCOUNTS)[0]) => {
    setEmail(acc.email);
    setPassword('TriNetraDemo!2026');
  };

  return (
    <main className="login">
      <section className="login-card">
        <div className="brand">
          <div className="mark">त्रि</div>
          <div>
            <h1>TriNetra</h1>
            <p>Explainable Multilingual Criminal Intelligence Graph</p>
          </div>
        </div>
        <Badge kind="demo">DEMO DATA — SYNTHETIC ENVIRONMENT</Badge>
        <h2>Authorized investigator sign in</h2>
        <form onSubmit={submit}>
          <label>
            Investigator Email
            <input value={email} type="email" onChange={(e) => setEmail(e.target.value)} required />
          </label>
          <label>
            Password
            <input value={password} type="password" onChange={(e) => setPassword(e.target.value)} required />
          </label>
          {err && <p className="error">{err}</p>}
          <button disabled={busy} type="submit">
            {busy ? 'Verifying credentials…' : 'Sign in securely'}
          </button>
        </form>

        <p className="muted" style={{ marginTop: '16px' }}>Quick-select demo role credentials:</p>
        <div className="demo-account-pills">
          {DEMO_ACCOUNTS.map((acc) => (
            <button key={acc.email} type="button" onClick={() => pickDemo(acc)}>
              {acc.name} ({acc.role})
            </button>
          ))}
        </div>
        <p className="muted" style={{ fontSize: '11px', marginTop: '10px' }}>
          Password: <code>TriNetraDemo!2026</code>. All records are entirely synthetic.
        </p>
      </section>
    </main>
  );
}

// -------------------------------------------------------------
// NAVIGATION COMPONENT
// -------------------------------------------------------------
function Nav({
  page,
  setPage,
  user,
  onLogout,
}: {
  page: string;
  setPage: (x: string) => void;
  user: Item;
  onLogout: () => void;
}) {
  const links = [
    ['overview', LayoutDashboard, 'Case Overview'],
    ['workspace', Network, 'Case Workspace'],
    ['graph', GitFork, 'Graph & Path Finder'],
    ['entities', Users, 'Entity Explorer'],
    ['matches', Shield, 'Identity Matches'],
    ['timeline', Clock, 'Chronological Timeline'],
    ['analytics', BarChart3, 'Analytics & Scores'],
    ['alerts', AlertTriangle, 'Alerts & Data Gaps'],
    ['copilot', Bot, 'Investigator Copilot'],
    ['documents', FolderOpen, 'Document Center'],
    ['reports', FileText, 'Reports & Dossiers'],
    ['audit', History, 'Audit Trail'],
  ];

  return (
    <aside aria-label="Main Navigation">
      <div className="side-brand">
        <span className="mark mini">त्रि</span>
        <b>TriNetra</b>
      </div>
      <Badge kind="demo">DEMO DATA</Badge>
      <nav>
        {links.map(([id, Icon, label]: any) => (
          <button
            aria-label={label}
            className={page === id ? 'active' : ''}
            onClick={() => setPage(id)}
            key={id}
          >
            <Icon size={17} />
            <span>{label}</span>
          </button>
        ))}
      </nav>
      <div className="user">
        <div className="user-info">
          <b>{user.name}</b>
          <small>
            {user.role} · {user.department || 'Demo Unit'}
          </small>
        </div>
        <button aria-label="Sign out" onClick={onLogout}>
          <LogOut size={15} />
          <span>Sign out</span>
        </button>
      </div>
    </aside>
  );
}

// -------------------------------------------------------------
// NEW CASE MODAL
// -------------------------------------------------------------
function NewCaseModal({
  token,
  onClose,
  onCreated,
  addToast,
}: {
  token: string;
  onClose: () => void;
  onCreated: (c: Item) => void;
  addToast: (msg: string, typ?: string) => void;
}) {
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [priority, setPriority] = useState('MEDIUM');
  const [busy, setBusy] = useState(false);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim() || !description.trim()) return;
    setBusy(true);
    try {
      const res = await api('/cases', token, {
        method: 'POST',
        body: JSON.stringify({ title, description, priority }),
      });
      addToast(`Case created: ${res.case_number}`, 'success');
      onCreated(res);
      onClose();
    } catch (e: any) {
      addToast(e.message, 'error');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="modal-title">
      <div className="modal-content">
        <header>
          <h2 id="modal-title">Create New Synthetic Case</h2>
          <button className="btn-secondary btn-small" onClick={onClose}>
            ✕
          </button>
        </header>
        <p className="muted" style={{ fontSize: '12px' }}>
          All created cases use isolated synthetic demonstration scope.
        </p>
        <form onSubmit={handleCreate} style={{ display: 'grid', gap: '12px' }}>
          <label>
            Case Title
            <input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Operation Varuna — Financial Lead Analysis"
              required
              minLength={3}
            />
          </label>
          <label>
            Scope Description
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Describe the synthetic investigation context and evidence scope..."
              required
              minLength={3}
              rows={3}
            />
          </label>
          <label>
            Investigation Priority
            <select value={priority} onChange={(e) => setPriority(e.target.value)}>
              <option value="LOW">LOW</option>
              <option value="MEDIUM">MEDIUM</option>
              <option value="HIGH">HIGH</option>
            </select>
          </label>
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '10px' }}>
            <button type="button" className="btn-secondary" onClick={onClose}>
              Cancel
            </button>
            <button type="submit" disabled={busy}>
              {busy ? 'Creating case…' : 'Create case'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// -------------------------------------------------------------
// OVERVIEW SCREEN
// -------------------------------------------------------------
function Overview({
  summary,
  caseData,
  onPage,
}: {
  summary: Item;
  caseData: Item;
  onPage: (x: string) => void;
}) {
  return (
    <>
      <header>
        <div>
          <p className="eyebrow">CASE OVERVIEW</p>
          <h1>{caseData.title}</h1>
          <p>
            {caseData.case_number} · <Badge kind="amber">{caseData.priority} PRIORITY</Badge>{' '}
            <Badge kind="blue">{caseData.status}</Badge>
          </p>
        </div>
        <button onClick={() => onPage('workspace')}>Open Case Workspace</button>
      </header>
      <Notice />
      <section className="stats">
        <Stat label="ENTITY RECORDS" value={summary.network?.nodes || '—'} sub="Synthetic, evidence-linked" />
        <Stat label="RELATIONSHIPS" value={summary.network?.relationships || '—'} sub="Within this case scope" />
        <Stat label="COMMUNITIES" value={summary.network?.communities || '—'} sub="Analytical graph clusters" />
        <Stat label="NETWORK DENSITY" value={summary.network?.density || '—'} sub="Degree connectivity metric" />
      </section>
      <section className="grid two">
        <article>
          <div className="section-title">
            <h2>Top Investigation Priority Leads</h2>
            <span>Explainable composite score</span>
          </div>
          <div className="ranking">
            {(summary.top_connections || []).map((x: Item, i: number) => (
              <div key={x.entity_id}>
                <span>0{i + 1}</span>
                <b>{x.name}</b>
                <i style={{ width: x.investigation_priority_score + '%' }}></i>
                <em>{x.investigation_priority_score}</em>
              </div>
            ))}
          </div>
          <p className="muted" style={{ fontSize: '12px' }}>
            Investigation priority cues reflect graph connectivity, bridge position, and synthetic evidence completeness, never culpability.
          </p>
        </article>
        <article>
          <div className="section-title">
            <h2>Responsible AI Guardrails</h2>
            <span>Enforced across system</span>
          </div>
          <ul className="guardrails">
            <li>Relationships do not establish guilt or illicit intent.</li>
            <li>Similar names never trigger automated identity merges.</li>
            <li>Inferred associations are clearly separated from observed facts.</li>
            <li>Confidence scores reflect record corroboration, not legal certainty.</li>
            <li>Authorized human investigator review is required prior to taking action.</li>
          </ul>
        </article>
      </section>
    </>
  );
}

// -------------------------------------------------------------
// GRAPH COMPONENT (Used in Workspace and Graph View)
// -------------------------------------------------------------
function GraphComponent({
  graph,
  onSelect,
  highlightEdgeIds = [],
  highlightNodeIds = [],
  filterType = '',
  minConfidence = 0,
}: {
  graph: Item;
  onSelect: (x: Item) => void;
  highlightEdgeIds?: string[];
  highlightNodeIds?: string[];
  filterType?: string;
  minConfidence?: number;
}) {
  const [query, setQuery] = useState('');
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const cyRef = useRef<any>(null);
  const panGuardRef = useRef(false);

  const els = useMemo(() => {
    const allNodes = graph.nodes || [];
    const allEdges = graph.edges || [];
    const idKey = (value: any) => String(value);
    const normalizedQuery = query.trim().toLowerCase();
    const selectedId = selectedNodeId ? idKey(selectedNodeId) : null;
    const matchingIds = new Set<string>(allNodes
      .filter((n: Item) => {
        const matchesQuery = !normalizedQuery || n.canonical_name.toLowerCase().includes(normalizedQuery);
        const matchesType = !filterType || n.entity_type === filterType;
        return matchesQuery && matchesType;
      })
      .map((n: Item) => idKey(n.id)));
    const visibleIds = new Set<string>(matchingIds);
    if (normalizedQuery) {
      allEdges.forEach((e: Item) => {
        const sourceId = idKey(e.source_entity_id);
        const targetId = idKey(e.target_entity_id);
        if (matchingIds.has(sourceId)) visibleIds.add(targetId);
        if (matchingIds.has(targetId)) visibleIds.add(sourceId);
      });
    }
    if (selectedId) {
      visibleIds.clear();
      visibleIds.add(selectedId);
      allEdges.forEach((e: Item) => {
        const sourceId = idKey(e.source_entity_id);
        const targetId = idKey(e.target_entity_id);
        if (sourceId === selectedId) visibleIds.add(targetId);
        if (targetId === selectedId) visibleIds.add(sourceId);
      });
    }

    const nodes = allNodes
      .filter((n: Item) => visibleIds.has(idKey(n.id)))
      .map((n: Item) => ({
        data: {
          id: idKey(n.id),
          label: n.canonical_name,
          type: n.entity_type,
          raw: n,
          isSearchMatch: matchingIds.has(idKey(n.id)),
          isPathNode: highlightNodeIds.map(idKey).includes(idKey(n.id)),
        },
      }));

    const nodeIds = new Set<string>(nodes.map((n: any) => idKey(n.data.id)));

    const edges = allEdges
      .filter((e: Item) => {
        const confOk = (e.confidence ?? 0) >= minConfidence;
        const endpointsExist = nodeIds.has(idKey(e.source_entity_id)) && nodeIds.has(idKey(e.target_entity_id));
        return confOk && endpointsExist;
      })
      .map((e: Item) => ({
        data: {
          id: idKey(e.id),
          source: idKey(e.source_entity_id),
          target: idKey(e.target_entity_id),
          label: e.relationship_type,
          origin: e.relationship_origin,
          isHighlighted: highlightEdgeIds.includes(e.id),
          raw: e,
        },
      }));

    return [...nodes, ...edges];
  }, [graph, query, filterType, minConfidence, highlightEdgeIds, selectedNodeId]);

  const searchSummary = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    if (!normalizedQuery) return null;

    const matches = (graph.nodes || []).filter((n: Item) => {
      const matchesName = n.canonical_name.toLowerCase().includes(normalizedQuery);
      const matchesType = !filterType || n.entity_type === filterType;
      return matchesName && matchesType;
    });
    if (!matches.length) return { matches: [], connections: [] };

    const matchIds = new Set(matches.map((n: Item) => n.id));
    const entityById = new Map((graph.nodes || []).map((n: Item) => [n.id, n]));
    const connections = (graph.edges || [])
      .filter((e: Item) => {
        const touchesMatch = matchIds.has(e.source_entity_id) || matchIds.has(e.target_entity_id);
        return touchesMatch && (e.confidence ?? 0) >= minConfidence;
      })
      .map((e: Item) => ({
        ...e,
        source: entityById.get(e.source_entity_id),
        target: entityById.get(e.target_entity_id),
      }));

    return { matches, connections };
  }, [graph, query, filterType, minConfidence]);

  const keepGraphInFrame = (cy: any) => {
    if (panGuardRef.current || !cy?.container() || !cy.nodes().length) return;
    const container = cy.container();
    const bounds = cy.nodes().renderedBoundingBox();
    const padding = 28;
    let shiftX = 0;
    let shiftY = 0;

    if (bounds.x2 < padding) shiftX = padding - bounds.x2;
    if (bounds.x1 > container.clientWidth - padding) shiftX = container.clientWidth - padding - bounds.x1;
    if (bounds.y2 < padding) shiftY = padding - bounds.y2;
    if (bounds.y1 > container.clientHeight - padding) shiftY = container.clientHeight - padding - bounds.y1;

    if (shiftX || shiftY) {
      panGuardRef.current = true;
      const pan = cy.pan();
      cy.pan({ x: pan.x + shiftX, y: pan.y + shiftY });
      panGuardRef.current = false;
    }
  };

  const fitGraphToViewport = (cy: any) => {
    if (!cy || !cy.elements().length) return;
    cy.fit(cy.elements(), 44);
    cy.minZoom(cy.zoom());
    keepGraphInFrame(cy);
  };

  const handleZoomIn = () => cyRef.current?.zoom(cyRef.current.zoom() * 1.25);
  const handleZoomOut = () => cyRef.current?.zoom(Math.max(cyRef.current.minZoom(), cyRef.current.zoom() * 0.8));
  const handleFit = () => fitGraphToViewport(cyRef.current);
  const handleGraphWheel = (event: React.WheelEvent<HTMLDivElement>) => {
    const cy = cyRef.current;
    if (!cy) return;
    const currentZoom = cy.zoom();
    const nextZoom = Math.min(
      cy.maxZoom(),
      Math.max(cy.minZoom(), currentZoom * (event.deltaY > 0 ? 0.9 : 1.1)),
    );
    if (nextZoom === currentZoom) return;
    event.preventDefault();
    cy.zoom(nextZoom);
  };

  return (
    <section className="graph-layout" aria-label="Case relationship graph">
      <article className="graph-card">
        <div className="toolbar">
          <div className="search">
            <Search size={15} />
            <input
              aria-label="Filter graph entities"
              placeholder="Search entity name..."
              value={query}
              onChange={(e) => {
                setQuery(e.target.value);
                setSelectedNodeId(null);
              }}
            />
            {query && <span className="search-hint">Matches + direct connections</span>}
          </div>
          <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
            <button className="btn-secondary btn-small" onClick={handleZoomIn} title="Zoom in">
              <ZoomIn size={14} />
            </button>
            <button className="btn-secondary btn-small" onClick={handleZoomOut} title="Zoom out">
              <ZoomOut size={14} />
            </button>
            <button className="btn-secondary btn-small" onClick={handleFit} title="Fit to screen">
              <Maximize2 size={14} />
            </button>
            <Badge kind="neutral">Zoom · Pan · Click node/edge</Badge>
          </div>
        </div>

        <div className="graph-viewport" onWheel={handleGraphWheel}>
          <CytoscapeComponent
            elements={els}
            style={{ width: '100%', height: '520px', background: '#09111d' }}
            layout={{
              name: 'cose',
              animate: false,
              fit: true,
              padding: 54,
              idealEdgeLength: 120,
              nodeRepulsion: 7000,
              gravity: 0.35,
            }}
            cy={(cy: any) => {
              cyRef.current = cy;
              cy.removeAllListeners();
              cy.autoungrabify(true);
              cy.panningEnabled(true);
              cy.userZoomingEnabled(false);
              cy.minZoom(0.1);
              cy.on('layoutstop', () => fitGraphToViewport(cy));
              cy.on('pan', () => keepGraphInFrame(cy));
              cy.on('dragfree', 'node', () => keepGraphInFrame(cy));
              cy.on('zoom', () => keepGraphInFrame(cy));
              cy.on('tap', 'node, edge', (evt: any) => {
                if (evt.target.isNode()) {
                  const clickedId = String(evt.target.id());
                  setSelectedNodeId((current) => current === clickedId ? null : clickedId);
                }
                onSelect(evt.target.data('raw'));
              });
              cy.on('tap', (evt: any) => {
                if (evt.target === cy) setSelectedNodeId(null);
              });
              requestAnimationFrame(() => fitGraphToViewport(cy));
            }}
            stylesheet={[
            {
              selector: 'node',
              style: {
                label: 'data(label)',
                'font-size': '8px',
                'background-color': '#3b82f6',
                color: '#e7efff',
                'text-outline-color': '#080e18',
                'text-outline-width': 2,
                width: 20,
                height: 20,
                'border-width': 1,
                'border-color': '#bfe9ff',
                'text-wrap': 'wrap',
                'text-max-width': 62,
              },
            },
            {
              selector: 'node[?isSearchMatch]',
              style: {
                width: 27,
                height: 27,
                'border-width': 2,
                'border-color': '#ffffff',
                'font-size': '9px',
                'z-index': 20,
              },
            },
            {
              selector: 'node[?isPathNode]',
              style: {
                'border-width': 4,
                'border-color': '#00e5ff',
                'z-index': 30,
              },
            },
            { selector: 'node[type = "Phone"]', style: { 'background-color': '#a855f7' } },
            { selector: 'node[type = "Vehicle"]', style: { 'background-color': '#f59e0b' } },
            { selector: 'node[type = "BankAccount"]', style: { 'background-color': '#22c55e' } },
            { selector: 'node[type = "Location"]', style: { 'background-color': '#06b6d4' } },
            { selector: 'node[type = "Organization"]', style: { 'background-color': '#ec4899' } },
            { selector: 'node[type = "CrimeEvent"]', style: { 'background-color': '#ef4444' } },
            {
              selector: 'edge',
              style: {
                width: 1.5,
                'line-color': '#3b5270',
                'target-arrow-color': '#3b5270',
                'target-arrow-shape': 'triangle',
                'curve-style': 'bezier',
                label: 'data(label)',
                'font-size': '6px',
                color: '#8ba2be',
              },
            },
            {
              selector: 'edge[origin = "INFERRED"]',
              style: {
                'line-style': 'dashed',
                'line-color': '#f59e0b',
                'target-arrow-color': '#f59e0b',
              },
            },
            {
              selector: 'edge[?isHighlighted]',
              style: {
                width: 4,
                'line-color': '#00e5ff',
                'target-arrow-color': '#00e5ff',
                color: '#00e5ff',
                'font-size': '9px',
                'z-index': 99,
              },
            },
          ]}
        />
        </div>

        {searchSummary && (
          <div className="graph-search-summary" aria-live="polite">
            {searchSummary.matches.length ? (
              <>
                <div className="graph-search-summary-header">
                  <div>
                    <span className="eyebrow">TEXT VIEW OF SEARCH</span>
                    <b>{searchSummary.matches.length} matching {searchSummary.matches.length === 1 ? 'entity' : 'entities'}</b>
                  </div>
                  <span className="muted">{searchSummary.connections.length} direct connection{searchSummary.connections.length === 1 ? '' : 's'}</span>
                </div>
                {searchSummary.matches.map((match: Item) => (
                  <div className="graph-search-entity" key={match.id}>
                    <div className="graph-search-entity-title">
                      <strong>{match.canonical_name}</strong>
                      <Badge kind="neutral">{match.entity_type}</Badge>
                    </div>
                    <div className="graph-connection-list">
                      {searchSummary.connections
                        .filter((e: Item) => e.source_entity_id === match.id || e.target_entity_id === match.id)
                        .map((e: Item) => {
                          const other = e.source_entity_id === match.id ? e.target : e.source;
                          return (
                            <div className="graph-connection" key={e.id}>
                              <span className="connection-dot" style={{ background: typeColors[other?.entity_type] || '#64748b' }} />
                              <b>{other?.canonical_name || 'Unknown entity'}</b>
                              <span>{e.relationship_type.replaceAll('_', ' ')}</span>
                              <small>{e.relationship_origin} · {Math.round((e.confidence || 0) * 100)}% confidence</small>
                            </div>
                          );
                        })}
                      {!searchSummary.connections.some((e: Item) => e.source_entity_id === match.id || e.target_entity_id === match.id) && (
                        <p className="muted">No connections meet the current confidence filter.</p>
                      )}
                    </div>
                  </div>
                ))}
              </>
            ) : (
              <p className="muted">No entity matches “{query}”. Try a full or partial name.</p>
            )}
          </div>
        )}

        <div className="legend">
          {Object.entries(typeColors).map(([x, c]) => (
            <span key={x}>
              <i style={{ background: c }} />
              {x}
            </span>
          ))}
          <span>━ Observed (Solid)</span>
          <span>┅ Inferred (Dashed)</span>
          <span>● Verified</span>
          <span>● Probable</span>
        </div>
      </article>
    </section>
  );
}

// -------------------------------------------------------------
// WORKSPACE SCREEN
// -------------------------------------------------------------
function Workspace({
  caseData,
  graph,
  selected,
  setSelected,
  docs,
  token,
  addToast,
}: {
  caseData: Item;
  graph: Item;
  selected: Item | null;
  setSelected: (x: Item | null) => void;
  docs: Item[];
  token: string;
  addToast: (msg: string, typ?: string) => void;
}) {
  const [evidenceData, setEvidenceData] = useState<Item | null>(null);
  const [loadingEv, setLoadingEv] = useState(false);

  // When an edge is selected, fetch evidence
  useEffect(() => {
    if (selected && selected.relationship_type && selected.id) {
      setLoadingEv(true);
      api(`/relationships/${selected.id}/evidence`, token)
        .then(setEvidenceData)
        .catch(() => setEvidenceData(null))
        .finally(() => setLoadingEv(false));
    } else {
      setEvidenceData(null);
    }
  }, [selected?.id, token]);

  const isEdge = Boolean(selected && selected.relationship_type);
  const selectedConnections = selected && !isEdge
    ? (graph.edges || [])
        .filter((e: Item) => e.source_entity_id === selected.id || e.target_entity_id === selected.id)
        .map((e: Item) => ({
          ...e,
          otherName: e.source_entity_id === selected.id ? e.target_entity_name : e.source_entity_name,
          otherType: e.source_entity_id === selected.id ? e.target_entity_type : e.source_entity_type,
        }))
    : [];

  const entityMeaning: Record<string, string> = {
    Person: 'A person record extracted from the case evidence.',
    Phone: 'A phone identifier linked to one or more recorded interactions.',
    Vehicle: 'A vehicle identifier appearing in the source records.',
    BankAccount: 'A bank account identifier appearing in synthetic transaction records.',
    Location: 'A location mentioned or observed in the case records.',
    Organization: 'An organization named in the case evidence.',
    CrimeEvent: 'A recorded incident or event from the case documents.',
  };

  return (
    <>
      <header>
        <div>
          <p className="eyebrow">PRIMARY EXPERIENCE</p>
          <h1>Case Workspace</h1>
          <p>This system provides analytical leads and does not establish guilt or final legal conclusions.</p>
        </div>
        <Badge kind="demo">SYNTHETIC SCOPE: {caseData.case_number}</Badge>
      </header>
      <div className="workspace">
        <GraphComponent graph={graph} onSelect={setSelected} />
        <article className="details" aria-live="polite">
          {selected ? (
            <>
              {isEdge ? (
                <>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <Badge kind={selected.relationship_origin === 'OBSERVED' ? 'blue' : 'amber'}>
                      {selected.relationship_origin} RELATIONSHIP
                    </Badge>
                    <Badge kind={selected.verification_status === 'VERIFIED' ? 'green' : 'amber'}>
                      {selected.verification_status}
                    </Badge>
                  </div>
                  <h2 style={{ marginTop: '10px' }}>
                    {selected.source_entity_name || 'Source'} → {selected.target_entity_name || 'Target'}
                  </h2>
                  <Badge kind="neutral">{selected.relationship_type}</Badge>

                  <dl>
                    <dt>Source Entity</dt>
                    <dd>{selected.source_entity_name} ({selected.source_entity_type})</dd>
                    <dt>Target Entity</dt>
                    <dd>{selected.target_entity_name} ({selected.target_entity_type})</dd>
                    <dt>Confidence</dt>
                    <dd>{Math.round((selected.confidence || 0) * 100)}%</dd>
                    <dt>Requires Verification</dt>
                    <dd>{selected.requires_verification ? 'YES' : 'No'}</dd>
                    <dt>Source Reference</dt>
                    <dd><code>{selected.source_reference}</code></dd>
                    <dt>Evidence Type</dt>
                    <dd>{selected.evidence_type}</dd>
                    {selected.amount && (
                      <>
                        <dt>Amount</dt>
                        <dd>₹{Number(selected.amount).toLocaleString('en-IN')}</dd>
                      </>
                    )}
                    {selected.observed_at && (
                      <>
                        <dt>Observed At</dt>
                        <dd>{selected.observed_at.replace('T', ' ').slice(0, 19)}</dd>
                      </>
                    )}
                  </dl>

                  <hr />
                  <h3>Evidence & Caveat</h3>
                  <p>{selected.explanation}</p>
                  <p className="recommend" style={{ fontSize: '11px', marginTop: '8px' }}>
                    {evidenceData?.caveat || 'Synthetic demo evidence; independently verify before operational use.'}
                  </p>
                </>
              ) : (
                <>
                  <div className="entity-inspector-heading">
                    <div>
                      <span className="eyebrow">ENTITY EVIDENCE SNAPSHOT</span>
                      <h2>{selected.canonical_name}</h2>
                    </div>
                    <Badge kind="neutral">{selected.entity_type}</Badge>
                  </div>
                  <div className="entity-status-row">
                    <Badge kind={selected.verification_status === 'VERIFIED' ? 'green' : 'amber'}>
                      {selected.verification_status === 'VERIFIED' ? 'VERIFIED RECORD' : 'REQUIRES VERIFICATION'}
                    </Badge>
                    <span className="muted">{selectedConnections.length} recorded connection{selectedConnections.length === 1 ? '' : 's'}</span>
                  </div>
                  <p className="entity-meaning">{entityMeaning[selected.entity_type] || 'An entity extracted from the case evidence.'}</p>

                  <div className="entity-facts">
                    <div>
                      <small>Evidence confidence</small>
                      <strong>{Math.round((selected.confidence || 0) * 100)}%</strong>
                      <div className="confidence-track"><i style={{ width: `${Math.round((selected.confidence || 0) * 100)}%` }} /></div>
                    </div>
                    <div>
                      <small>Source text</small>
                      <strong>{selected.source_text_span || 'Synthetic seed record'}</strong>
                    </div>
                    <div>
                      <small>Evidence method</small>
                      <strong>{selected.extraction_method || 'Record extraction'}</strong>
                    </div>
                  </div>

                  <h3>Connected Evidence</h3>
                  {selectedConnections.length ? (
                    <div className="entity-connections">
                      {selectedConnections.slice(0, 8).map((connection: Item) => (
                        <div className="entity-connection" key={connection.id}>
                          <div>
                            <b>{connection.otherName || 'Unknown entity'}</b>
                            <small>{connection.otherType || 'Entity'}</small>
                          </div>
                          <span>{connection.relationship_type.replaceAll('_', ' ')}</span>
                          <small>{connection.relationship_origin} · {Math.round((connection.confidence || 0) * 100)}%</small>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="muted">No relationship is currently recorded for this entity.</p>
                  )}

                  <details className="technical-details">
                    <summary>View technical identifiers</summary>
                    <dl>
                      <dt>Normalized ID</dt>
                      <dd><code>{selected.normalized_value}</code></dd>
                      <dt>Source document</dt>
                      <dd><code>{selected.source_document_id?.slice(0, 12) || 'Not available'}...</code></dd>
                    </dl>
                  </details>

                  <div className="investigator-note">
                    <b>Investigator note:</b> This is an evidence-linked analytical lead, not a conclusion. Confirm identity and context from the original source documents before action.
                  </div>
                </>
              )}
            </>
          ) : (
            <div className="empty">
              <Network size={36} style={{ opacity: 0.4, marginBottom: '8px' }} />
              <p><b>Select a node or edge</b> in the graph to inspect evidence citations, confidence, and source explanations.</p>
              <p className="muted" style={{ fontSize: '11px' }}>
                Observed links reflect recorded records; inferred links represent potential associations that require human verification.
              </p>
            </div>
          )}

          <hr />
          <h3>Case Evidence Inventory</h3>
          <p className="muted" style={{ fontSize: '12px' }}>
            {docs.length} synthetic source documents linked to this case scope.
          </p>
        </article>
      </div>
    </>
  );
}

// -------------------------------------------------------------
// GRAPH & PATH FINDER VIEW
// -------------------------------------------------------------
function GraphView({
  graph,
  caseId,
  token,
  addToast,
}: {
  graph: Item;
  caseId: string;
  token: string;
  addToast: (msg: string, typ?: string) => void;
}) {
  const [selectedItem, setSelectedItem] = useState<Item | null>(null);
  const [filterType, setFilterType] = useState('');
  const [minConf, setMinConf] = useState(0);
  const [srcId, setSrcId] = useState('');
  const [tgtId, setTgtId] = useState('');
  const [pathResult, setPathResult] = useState<Item | null>(null);
  const [searchingPath, setSearchingPath] = useState(false);

  const nodes = graph.nodes || [];
  const observedCount = (graph.edges || []).filter((e: Item) => e.relationship_origin === 'OBSERVED').length;
  const inferredCount = (graph.edges || []).filter((e: Item) => e.relationship_origin === 'INFERRED').length;
  const pathNodeIds = useMemo<string[]>(() => {
    if (!pathResult?.edges?.length) return [];
    return Array.from(new Set<string>(pathResult.edges.flatMap((e: Item) => [e.source_entity_id, e.target_entity_id])));
  }, [pathResult]);

  const handleFindPath = async () => {
    if (!srcId || !tgtId || srcId === tgtId) {
      addToast('Please select two distinct entities.', 'error');
      return;
    }
    setSearchingPath(true);
    setPathResult(null);
    try {
      const res = await api(`/cases/${caseId}/graph/path?source=${srcId}&target=${tgtId}`, token);
      setPathResult(res);
      if (res.edge_ids?.length) {
        addToast(`Path found with ${res.edge_ids.length} step(s).`, 'success');
      } else {
        addToast('No analytical path found between entities in this case scope.', 'info');
      }
    } catch (e: any) {
      addToast(e.message, 'error');
    } finally {
      setSearchingPath(false);
    }
  };

  return (
    <>
      <header>
        <div>
          <p className="eyebrow">GRAPH EXPLORER & PATH FINDER</p>
          <h1>Network Graph & Analytical Traversal</h1>
          <p>Examine case-scoped relationships and trace multi-hop connectivity between synthetic entities.</p>
        </div>
      </header>

      <section className="network-purpose" aria-label="Network graph purpose">
        <div className="network-purpose-copy">
          <span className="eyebrow">WHAT THIS VIEW DOES</span>
          <h2>See how evidence records connect</h2>
          <p>
            Use the network to inspect who or what is connected inside this case. Select a node to review its evidence, or choose two entities below to trace the shortest relationship route between them.
          </p>
        </div>
        <div className="network-purpose-stats">
          <div><strong>{nodes.length}</strong><span>entities</span></div>
          <div><strong>{graph.edges?.length || 0}</strong><span>relationships</span></div>
          <div><strong>{observedCount}</strong><span>observed</span></div>
          <div><strong>{inferredCount}</strong><span>inferred leads</span></div>
        </div>
      </section>

      <div className="path-finder">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <span className="eyebrow">INVESTIGATION TASK</span>
            <b>Trace how two entities are connected</b>
          </div>
          <small className="muted">Select a starting point and destination</small>
        </div>
        <div className="path-finder-controls">
          <select value={srcId} onChange={(e) => setSrcId(e.target.value)}>
            <option value="">-- Select Source Entity --</option>
            {nodes.map((n: Item) => (
              <option key={n.id} value={n.id}>
                {n.canonical_name} ({n.entity_type})
              </option>
            ))}
          </select>
          <span className="muted">→</span>
          <select value={tgtId} onChange={(e) => setTgtId(e.target.value)}>
            <option value="">-- Select Target Entity --</option>
            {nodes.map((n: Item) => (
              <option key={n.id} value={n.id}>
                {n.canonical_name} ({n.entity_type})
              </option>
            ))}
          </select>
          <button disabled={searchingPath || !srcId || !tgtId} onClick={handleFindPath}>
            {searchingPath ? 'Tracing evidence route…' : 'Trace Evidence Route'}
          </button>
          {pathResult && (
            <button className="btn-secondary btn-small" onClick={() => setPathResult(null)}>
              Clear Path
            </button>
          )}
        </div>

        {pathResult && (
          <div className="path-result">
            <div className="path-result-header">
              <div>
                <span className="eyebrow">ANALYTICAL ROUTE</span>
                <b>{pathResult.length ? `${pathResult.length} relationship steps identified` : 'No connecting route identified'}</b>
              </div>
              <Badge kind={pathResult.length ? 'blue' : 'neutral'}>{pathResult.length ? 'REVIEW ROUTE' : 'NO PATH'}</Badge>
            </div>
            {pathResult.length > 0 && (
              <div className="route-overview">
                <div>
                  <small>START ENTITY</small>
                  <strong>{nodes.find((n: Item) => n.id === srcId)?.canonical_name || 'Selected source'}</strong>
                </div>
                <span className="route-arrow">→</span>
                <div>
                  <small>DESTINATION ENTITY</small>
                  <strong>{nodes.find((n: Item) => n.id === tgtId)?.canonical_name || 'Selected target'}</strong>
                </div>
              </div>
            )}
            {pathResult.length > 0 && (
              <div className="route-stats">
                <span><b>{pathResult.edges.filter((e: Item) => e.relationship_origin === 'OBSERVED').length}</b> observed records</span>
                <span><b>{pathResult.edges.filter((e: Item) => e.relationship_origin === 'INFERRED').length}</b> inferred leads</span>
                <span><b>{pathResult.edges.filter((e: Item) => e.requires_verification).length}</b> require verification</span>
              </div>
            )}
            <p className="path-explanation">{pathResult.message}</p>
            {pathResult.length > 0 && (
              <p className="route-review-note"><b>How to read this:</b> Follow the numbered links from start to destination. Solid observed records are source-backed; dashed inferred leads need independent corroboration.</p>
            )}
            {pathResult.edges?.length > 0 && (
              <ol className="path-steps">
                {pathResult.edges.map((e: Item, idx: number) => (
                  <li key={e.id}>
                    <div>
                      <strong>{e.source_entity_name || e.source_entity_id}</strong>
                      <span className="path-link">{e.relationship_type.replaceAll('_', ' ')} · {Math.round(e.confidence * 100)}% confidence</span>
                      <strong>{e.target_entity_name || e.target_entity_id}</strong>
                    </div>
                    <small>{e.relationship_origin === 'OBSERVED' ? 'Observed record' : 'Inferred lead requiring verification'}</small>
                  </li>
                ))}
              </ol>
            )}
          </div>
        )}
      </div>

      <div style={{ display: 'flex', gap: '10px', alignItems: 'center', marginBottom: '14px', flexWrap: 'wrap' }}>
        <span className="muted" style={{ fontSize: '12px' }}>Filter Entity Type:</span>
        {['', 'Person', 'Phone', 'Vehicle', 'BankAccount', 'Location', 'Organization', 'CrimeEvent'].map((typ) => (
          <button
            key={typ}
            className={'btn-small ' + (filterType === typ ? '' : 'btn-secondary')}
            onClick={() => setFilterType(typ)}
          >
            {typ || 'All Entities'}
          </button>
        ))}

        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span className="muted" style={{ fontSize: '12px' }}>Min Confidence:</span>
          <input
            type="range"
            min="0"
            max="1"
            step="0.05"
            value={minConf}
            onChange={(e) => setMinConf(parseFloat(e.target.value))}
            style={{ width: '100px' }}
          />
          <Badge kind="neutral">{Math.round(minConf * 100)}%</Badge>
        </div>
      </div>

      <GraphComponent
        graph={graph}
        onSelect={setSelectedItem}
        highlightEdgeIds={pathResult?.edge_ids || []}
        highlightNodeIds={pathNodeIds}
        filterType={filterType}
        minConfidence={minConf}
      />

      {selectedItem && (
        <article className="network-selection" aria-live="polite">
          <div className="network-selection-header">
            <div>
              <span className="eyebrow">SELECTED EVIDENCE</span>
              <h2>{selectedItem.canonical_name || `${selectedItem.source_entity_name || 'Entity'} → ${selectedItem.target_entity_name || 'Target'}`}</h2>
            </div>
            <Badge kind="neutral">{selectedItem.entity_type || selectedItem.relationship_type}</Badge>
          </div>
          {selectedItem.relationship_type ? (
            <p>
              This relationship is a <b>{selectedItem.relationship_type.replaceAll('_', ' ').toLowerCase()}</b> record with {Math.round((selectedItem.confidence || 0) * 100)}% confidence. It is {selectedItem.relationship_origin === 'OBSERVED' ? 'directly observed in the source records.' : 'an inferred lead and needs independent verification.'}
            </p>
          ) : (
            <p>This entity is part of the case network. Open <b>Case Workspace</b> for its full evidence snapshot and connected records.</p>
          )}
          <div className="network-selection-actions">
            <span className="muted">Use the path finder above to compare this entity with another one.</span>
            <button className="btn-secondary btn-small" onClick={() => setSelectedItem(null)}>Clear selection</button>
          </div>
        </article>
      )}
    </>
  );
}

// -------------------------------------------------------------
// ENTITY EXPLORER VIEW
// -------------------------------------------------------------
function Entities({
  entities,
  onSelectEntity,
}: {
  entities: Item[];
  onSelectEntity: (x: Item) => void;
}) {
  const [q, setQ] = useState('');
  const [typeFilter, setTypeFilter] = useState('');

  const rows = entities.filter((x) => {
    const matchesQ = x.canonical_name.toLowerCase().includes(q.toLowerCase());
    const matchesType = !typeFilter || x.entity_type === typeFilter;
    return matchesQ && matchesType;
  });

  return (
    <>
      <header>
        <div>
          <p className="eyebrow">ENTITY EXPLORER</p>
          <h1>Evidence-Linked Entities</h1>
          <p>Inspect extracted and resolved entities associated with the active synthetic case.</p>
        </div>
      </header>

      <div style={{ display: 'flex', gap: '10px', alignItems: 'center', marginBottom: '14px', flexWrap: 'wrap' }}>
        <div className="search wide" style={{ margin: 0, flex: 1 }}>
          <Search size={16} />
          <input
            placeholder="Search people, phones, vehicles, bank accounts, locations..."
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
        </div>
        {['', 'Person', 'Phone', 'Vehicle', 'BankAccount', 'Location', 'Organization'].map((t) => (
          <button
            key={t}
            className={'btn-small ' + (typeFilter === t ? '' : 'btn-secondary')}
            onClick={() => setTypeFilter(t)}
          >
            {t || 'All Types'}
          </button>
        ))}
      </div>

      <article className="table">
        <div className="row head">
          <span>Name / Canonical Value</span>
          <span>Entity Type</span>
          <span>Extraction Confidence</span>
          <span>Verification Status</span>
        </div>
        {rows.map((x) => (
          <button className="row" key={x.id} onClick={() => onSelectEntity(x)}>
            <b>{x.canonical_name}</b>
            <span>
              <Badge kind="neutral">{x.entity_type}</Badge>
            </span>
            <span>{Math.round(x.confidence * 100)}%</span>
            <span>
              <Badge kind={x.verification_status === 'VERIFIED' ? 'green' : 'amber'}>
                {x.verification_status}
              </Badge>
            </span>
          </button>
        ))}
        {!rows.length && <p className="empty">No matching entities found in current case scope.</p>}
      </article>
    </>
  );
}

// -------------------------------------------------------------
// IDENTITY MATCHES (ENTITY RESOLUTION) VIEW
// -------------------------------------------------------------
function Matches({
  caseId,
  entities,
  token,
  userRole,
  addToast,
}: {
  caseId: string;
  entities: Item[];
  token: string;
  userRole: string;
  addToast: (msg: string, typ?: string) => void;
}) {
  const [pairs, setPairs] = useState<Item[]>([]);
  const [loading, setLoading] = useState(false);
  const [decisions, setDecisions] = useState<Record<string, string>>({});

  const canDecide = ['ADMIN', 'SUPERVISOR'].includes(userRole);

  useEffect(() => {
    setLoading(true);
    api(`/cases/${caseId}/entity-resolution/pairs`, token)
      .then(setPairs)
      .catch((e: any) => addToast(e.message, 'error'))
      .finally(() => setLoading(false));
  }, [caseId, token]);

  const handleDecision = async (matchId: string, decision: 'confirm' | 'reject' | 'uncertain' | 'undo') => {
    if (!canDecide) {
      addToast('Role restriction: Only Supervisors and Admins can record match decisions.', 'error');
      return;
    }
    try {
      const res = await api(`/entity-matches/${matchId}/${decision}`, token, { method: 'POST' });
      setDecisions((prev) => ({ ...prev, [matchId]: res.status }));
      addToast(res.message, 'success');
    } catch (e: any) {
      addToast(e.message, 'error');
    }
  };

  return (
    <>
      <header>
        <div>
          <p className="eyebrow">HUMAN-IN-THE-LOOP ENTITY RESOLUTION</p>
          <h1>Reviewable Identity Matches</h1>
          <p>Names alone never merge records. All review decisions are auditable and reversible.</p>
        </div>
        <Badge kind="demo">DEMO RESOLUTION ENGINE</Badge>
      </header>

      <Notice />

      {loading ? (
        <div className="skeleton">Evaluating entity candidate pairs…</div>
      ) : (
        <div style={{ display: 'grid', gap: '14px' }}>
          {pairs.map((p) => {
            const currentStatus = decisions[p.id] || p.status;
            return (
              <article className="match-card" key={p.id}>
                <div className="match-header">
                  <div>
                    <h3 style={{ margin: 0 }}>
                      {p.source_entity?.canonical_name} ⟷ {p.target_entity?.canonical_name}
                    </h3>
                    <small className="muted">
                      Entity Comparison ({p.source_entity?.entity_type})
                    </small>
                  </div>
                  <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                    <Badge kind={p.match_category === 'PROBABLE' ? 'amber' : 'neutral'}>
                      {p.match_category} MATCH ({Math.round(p.match_score * 100)}%)
                    </Badge>
                    <Badge
                      kind={
                        currentStatus === 'CONFIRMED'
                          ? 'green'
                          : currentStatus === 'REJECTED'
                          ? 'red'
                          : 'neutral'
                      }
                    >
                      STATUS: {currentStatus}
                    </Badge>
                  </div>
                </div>

                <div className="match-score-bar">
                  <div
                    className="match-score-fill"
                    style={{
                      width: p.match_score * 100 + '%',
                      background: p.match_score >= 0.8 ? '#f59e0b' : '#38bdf8',
                    }}
                  />
                </div>

                <div className="match-fields">
                  <div>
                    <b>Matching Fields / Rationales:</b>
                    <ul style={{ margin: '4px 0 0', paddingLeft: '16px' }}>
                      {p.reasons.map((r: string) => (
                        <li key={r}>{r}</li>
                      ))}
                    </ul>
                  </div>
                  <div>
                    <b>Conflicting & Missing Fields:</b>
                    <ul style={{ margin: '4px 0 0', paddingLeft: '16px' }}>
                      {p.conflicting_fields.map((c: string) => (
                        <li key={c} style={{ color: '#ffb3aa' }}>
                          {c}
                        </li>
                      ))}
                      {p.missing_fields.map((m: string) => (
                        <li key={m} style={{ color: '#fcd34d' }}>
                          Missing: {m}
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>

                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '4px' }}>
                  <small className="muted">
                    Supporting synthetic evidence: {p.supporting_evidence.join(', ') || 'None'}
                  </small>
                  <div className="decisions">
                    <button
                      className="btn-small"
                      disabled={!canDecide}
                      onClick={() => handleDecision(p.id, 'confirm')}
                      title={!canDecide ? 'Supervisor or Admin role required' : ''}
                    >
                      Confirm Match
                    </button>
                    <button
                      className="btn-small btn-secondary"
                      disabled={!canDecide}
                      onClick={() => handleDecision(p.id, 'reject')}
                    >
                      Reject
                    </button>
                    <button
                      className="btn-small btn-secondary"
                      disabled={!canDecide}
                      onClick={() => handleDecision(p.id, 'uncertain')}
                    >
                      Mark Uncertain
                    </button>
                    <button
                      className="btn-small btn-secondary"
                      disabled={!canDecide}
                      onClick={() => handleDecision(p.id, 'undo')}
                    >
                      Undo
                    </button>
                  </div>
                </div>
              </article>
            );
          })}
          {!pairs.length && (
            <p className="empty">No candidate entity pairs requiring resolution in this case.</p>
          )}
        </div>
      )}
    </>
  );
}

// -------------------------------------------------------------
// CHRONOLOGICAL TIMELINE VIEW
// -------------------------------------------------------------
function TimelineView({
  caseId,
  token,
  addToast,
}: {
  caseId: string;
  token: string;
  addToast: (msg: string, typ?: string) => void;
}) {
  const [items, setItems] = useState<Item[]>([]);
  const [loading, setLoading] = useState(false);
  const [categoryFilter, setCategoryFilter] = useState('');
  const [searchQ, setSearchQ] = useState('');

  useEffect(() => {
    setLoading(true);
    api(`/cases/${caseId}/timeline`, token)
      .then((res) => setItems(res.timeline || []))
      .catch((e: any) => addToast(e.message, 'error'))
      .finally(() => setLoading(false));
  }, [caseId, token]);

  const filtered = items.filter((it) => {
    const matchesCat = !categoryFilter || it.relationship_type === categoryFilter || it.category === categoryFilter;
    const textStr = `${it.source_entity_name} ${it.target_entity_name} ${it.relationship_type} ${it.source_reference}`.toLowerCase();
    const matchesQ = !searchQ || textStr.includes(searchQ.toLowerCase());
    return matchesCat && matchesQ;
  });

  return (
    <>
      <header>
        <div>
          <p className="eyebrow">CHRONOLOGICAL EVENT STREAM</p>
          <h1>Investigation Activity Timeline</h1>
          <p>Sequenced synthetic events, communications, financial transfers, and sightings.</p>
        </div>
      </header>

      <div style={{ display: 'flex', gap: '10px', alignItems: 'center', marginBottom: '16px', flexWrap: 'wrap' }}>
        <div className="search" style={{ flex: 1, maxWidth: '320px', margin: 0 }}>
          <Search size={15} />
          <input placeholder="Filter timeline events..." value={searchQ} onChange={(e) => setSearchQ(e.target.value)} />
        </div>
        {['', 'CALLED', 'TRANSFERRED_MONEY_TO', 'VISITED', 'USED_PHONE', 'CRIME_EVENT'].map((cat) => (
          <button
            key={cat}
            className={'btn-small ' + (categoryFilter === cat ? '' : 'btn-secondary')}
            onClick={() => setCategoryFilter(cat)}
          >
            {cat.replace('_', ' ') || 'All Events'}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="skeleton">Assembling case timeline…</div>
      ) : (
        <div className="timeline-list">
          {filtered.map((item) => {
            const isCrime = item.category === 'CRIME_EVENT';
            const isFin = item.relationship_type === 'TRANSFERRED_MONEY_TO';
            return (
              <div
                key={item.id}
                className={`timeline-item ${isCrime ? 'crime-event' : isFin ? 'financial' : ''}`}
              >
                <div className="timeline-header">
                  <div>
                    <Badge kind={isCrime ? 'red' : isFin ? 'green' : 'blue'}>
                      {item.relationship_type}
                    </Badge>{' '}
                    <Badge kind="neutral">{item.origin}</Badge>
                    <b style={{ marginLeft: '10px', fontSize: '14px' }}>
                      {item.source_entity_name} {isCrime ? '' : `→ ${item.target_entity_name}`}
                    </b>
                  </div>
                  <span className="timeline-time">
                    {item.timestamp ? item.timestamp.replace('T', ' ').slice(0, 19) : 'Timestamp pending'}
                  </span>
                </div>
                <p style={{ margin: '4px 0', fontSize: '13px' }}>{item.explanation}</p>
                <div style={{ display: 'flex', gap: '12px', fontSize: '11px', color: '#889eb7', marginTop: '6px' }}>
                  <span>Source: <code>{item.source_reference}</code></span>
                  <span>Confidence: {Math.round(item.confidence * 100)}%</span>
                  {item.amount && <span>Amount: ₹{Number(item.amount).toLocaleString('en-IN')}</span>}
                  <span>Type: {item.evidence_type}</span>
                </div>
              </div>
            );
          })}
          {!filtered.length && <p className="empty">No timeline events match the filter.</p>}
        </div>
      )}
    </>
  );
}

// -------------------------------------------------------------
// ANALYTICS SCREEN
// -------------------------------------------------------------
function Analytics({ summary }: { summary: Item }) {
  const temporal = summary.temporal_activity || [];
  const totalEvents = temporal.reduce((total: number, item: Item) => total + Number(item.count || 0), 0);
  const peakActivity = temporal.reduce((peak: Item | null, item: Item) => (
    !peak || Number(item.count || 0) > Number(peak.count || 0) ? item : peak
  ), null);
  const topLead = summary.top_connections?.[0];

  return (
    <>
      <header>
        <div>
          <p className="eyebrow">ANALYTICS & EXPLAINABILITY</p>
          <h1>Explainable Network Signals</h1>
          <p>Analytical indicators direct investigator review; they are not criminal scores.</p>
        </div>
      </header>

      <section className="analytics-purpose" aria-label="Analytics interpretation">
        <div>
          <span className="eyebrow">WHAT THIS SCREEN SHOWS</span>
          <h2>When activity happened and why a lead is surfaced</h2>
          <p>Use the activity bars to find dates that deserve source-document review. Use the priority breakdown to understand which evidence signals contributed to a lead. Neither view proves identity, intent, or guilt.</p>
        </div>
        <div className="analytics-callouts">
          <div><strong>{totalEvents}</strong><span>timestamped records</span></div>
          <div><strong>{peakActivity ? peakActivity.date : '—'}</strong><span>peak activity date</span></div>
          <div><strong>{topLead?.name || '—'}</strong><span>top review lead</span></div>
        </div>
      </section>

      <section className="grid two">
        <article>
          <div className="section-title">
            <div>
              <h2>Evidence Activity by Date</h2>
              <p className="chart-subtitle">Taller bar = more timestamped relationship records on that date</p>
            </div>
            <span>{totalEvents} records</span>
          </div>
          <div className="bars">
            {temporal.map((x: Item) => (
              <div key={x.date} title={`${x.date}: ${x.count} timestamped record${x.count === 1 ? '' : 's'}`}>
                <b>{x.count}</b>
                <i style={{ height: Math.min(180, x.count * 8) + 'px' }}></i>
                <small>{x.date.slice(5)}</small>
              </div>
            ))}
          </div>
          <p className="muted" style={{ fontSize: '11px', marginTop: '10px' }}>
            Start with the peak date, then open the Timeline and source documents to verify what happened and whether multiple records describe the same activity.
          </p>
        </article>

        <article>
          <div className="section-title">
            <div>
              <h2>Why a Lead Is Prioritized</h2>
              <p className="chart-subtitle">Review signal contribution, not a guilt score</p>
            </div>
            <span>100% total</span>
          </div>
          <dl className="score">
            <dt>Network Position (30%)</dt>
            <dd>Degree centrality, 2-hop reach, and connection volume</dd>
            <dt>Cross-Community Bridge (25%)</dt>
            <dd>Potential links connecting otherwise disparate clusters</dd>
            <dt>Temporal Activity (20%)</dt>
            <dd>Interaction bursts and frequency of recent synthetic events</dd>
            <dt>Evidence Quality (15%)</dt>
            <dd>Average confidence of supporting documents and records</dd>
            <dt>Data Completeness (10%)</dt>
            <dd>Penalty for unverified identities or open data-quality gaps</dd>
          </dl>
          <div className="recommend" style={{ marginTop: '14px', fontSize: '11px' }}>
            <b>Investigator use:</b> A high priority means the records deserve structured review first. Check the supporting relationships, confidence, open data gaps, and original documents before taking action.
          </div>
        </article>
      </section>
    </>
  );
}

// -------------------------------------------------------------
// ALERTS & DATA GAPS SCREEN
// -------------------------------------------------------------
function Alerts({ alerts, gaps }: { alerts: Item[]; gaps: Item[] }) {
  return (
    <>
      <header>
        <div>
          <p className="eyebrow">ALERTS & INFORMATION AUDIT</p>
          <h1>Reviewable Leads & Data Gaps</h1>
          <p>Flagged patterns and missing corroborating data requiring investigator action.</p>
        </div>
      </header>
      <div className="grid two">
        <article>
          <h2>Actionable Pattern Alerts</h2>
          {alerts.map((a) => (
            <div className="alert" key={a.id}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Badge kind={a.severity === 'HIGH' ? 'red' : 'amber'}>{a.severity} SEVERITY</Badge>
                <small className="muted">Confidence: {Math.round(a.confidence * 100)}%</small>
              </div>
              <h3>{a.title}</h3>
              <p>{a.description}</p>
              <div className="recommend">
                <b>Verification Action:</b> {a.recommended_action}
              </div>
              <small className="muted" style={{ display: 'block', marginTop: '6px' }}>
                Evidence References: {a.evidence_ids?.length || 0} records cited
              </small>
            </div>
          ))}
          {!alerts.length && <p className="empty">No open alerts for this case.</p>}
        </article>

        <article>
          <h2>Investigation Data-Gap Finder</h2>
          {gaps.map((g) => (
            <div className="gap" key={g.id}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Badge kind={g.severity === 'HIGH' ? 'red' : 'amber'}>{g.severity} IMPACT</Badge>
                <Badge kind="neutral">{g.status}</Badge>
              </div>
              <h3>{g.description}</h3>
              <p><b>Recommended Action:</b> {g.recommended_action}</p>
            </div>
          ))}
          {!gaps.length && <p className="empty">No open data gaps detected.</p>}
        </article>
      </div>
    </>
  );
}

// -------------------------------------------------------------
// COPILOT SCREEN
// -------------------------------------------------------------
function Copilot({ caseId, token }: { caseId: string; token: string }) {
  const [q, setQ] = useState('What data gaps affect this case?');
  const [answer, setAnswer] = useState<Item | null>(null);
  const [busy, setBusy] = useState(false);

  const ask = async (e?: React.FormEvent, customQuery?: string) => {
    e?.preventDefault();
    const queryToSend = customQuery || q;
    if (!queryToSend.trim()) return;
    setBusy(true);
    try {
      const res = await api(`/cases/${caseId}/copilot/query`, token, {
        method: 'POST',
        body: JSON.stringify({ query: queryToSend }),
      });
      setAnswer(res);
    } finally {
      setBusy(false);
    }
  };

  const suggestions = [
    'Show all people connected to vehicle DL01AB1234 within two hops.',
    'Why is Imran marked as a high-priority investigative lead?',
    'Summarize the network in Hindi.',
    'What data gaps affect this case?',
    'Summarize synthetic financial transfers.',
    'Analyze phone communication patterns.',
  ];

  return (
    <>
      <header>
        <div>
          <p className="eyebrow">GROUNDED INVESTIGATOR COPILOT</p>
          <h1>Evidence-Grounded Intelligence Assistant</h1>
          <p>Answers are computed strictly from retrieved case evidence; never uses external LLMs or unverified facts.</p>
        </div>
      </header>

      <article className="copilot">
        <div className="suggestions">
          {suggestions.map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => {
                setQ(s);
                ask(undefined, s);
              }}
            >
              {s}
            </button>
          ))}
        </div>

        <form onSubmit={(e) => ask(e)}>
          <textarea
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Ask a question about the synthetic evidence in this case..."
          />
          <button disabled={busy} type="submit">
            {busy ? 'Analyzing evidence…' : 'Ask Copilot'}
          </button>
        </form>

        {answer && (
          <div className="answer">
            <Badge kind="blue">{answer.label}</Badge>
            <h2>{answer.direct_answer}</h2>

            <h3 style={{ marginTop: '16px' }}>Evidence Used & Grounding Citations</h3>
            <ul>
              {(answer.evidence_used || []).map((x: string) => (
                <li key={x}><code>{x}</code></li>
              ))}
            </ul>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px', marginTop: '14px', fontSize: '12px' }}>
              <div>
                <b>Confidence:</b> {Math.round(answer.confidence * 100)}%
              </div>
              <div>
                <b>Data Limitations:</b> {answer.data_limitations}
              </div>
            </div>

            <div className="recommend" style={{ marginTop: '12px' }}>
              <b>Suggested Verification:</b> {answer.suggested_verification_action}
            </div>
          </div>
        )}
      </article>
    </>
  );
}

// -------------------------------------------------------------
// DOCUMENT CENTER SCREEN
// -------------------------------------------------------------
function DocumentsView({
  caseId,
  token,
  docs,
  setDocs,
  userRole,
  addToast,
}: {
  caseId: string;
  token: string;
  docs: Item[];
  setDocs: (x: Item[]) => void;
  userRole: string;
  addToast: (msg: string, typ?: string) => void;
}) {
  const [uploading, setUploading] = useState(false);
  const [extractedEntities, setExtractedEntities] = useState<Item[]>([]);
  const [selectedDocument, setSelectedDocument] = useState('');
  const fileInputRef = useRef<HTMLInputElement>(null);
  const canUpload = ['ADMIN', 'SUPERVISOR', 'INVESTIGATOR'].includes(userRole);

  const handleUpload = async (file: File) => {
    if (!canUpload) {
      addToast('Viewer and Analyst roles cannot upload documents.', 'error');
      return;
    }
    if (file.size > 10_000_000) {
      addToast('File exceeds the 10 MB demo limit.', 'error');
      return;
    }
    setUploading(true);
    const formData = new FormData();
    formData.append('file', file);
    try {
      const r = await fetch(`${API}/cases/${caseId}/documents`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: formData,
      });
      if (!r.ok) {
        const err = await r.json().catch(() => ({ detail: 'Upload failed' }));
        throw new Error(err.detail || 'Upload failed');
      }
      const res = await r.json();
      if (res.idempotent) {
        addToast(res.message, 'info');
      } else {
        addToast(`Uploaded: ${res.document?.filename}`, 'success');
        setDocs([res.document, ...docs]);
      }
    } catch (e: any) {
      addToast(e.message, 'error');
    } finally {
      setUploading(false);
    }
  };

  const handleProcess = async (docId: string) => {
    if (!canUpload) {
      addToast('Viewer and Analyst roles cannot process documents.', 'error');
      return;
    }
    try {
      const res = await api(`/documents/${docId}/process`, token, { method: 'POST' });
      addToast(`Extracted ${res.entities_extracted} entities from document.`, 'success');
    } catch (e: any) {
      addToast(e.message, 'error');
    }
  };

  const inspectExtraction = async (doc: Item) => {
    try {
      const res = await api(`/documents/${doc.id}/content`, token);
      setSelectedDocument(doc.filename);
      setExtractedEntities(res.entities || []);
    } catch (e: any) {
      addToast(e.message, 'error');
    }
  };

  const confidenceKind = (confidence: number) => confidence >= 0.8 ? 'green' : confidence >= 0.5 ? 'amber' : 'red';

  return (
    <>
      <header>
        <div>
          <p className="eyebrow">DOCUMENT CENTER</p>
          <h1>Evidence Ingestion & Document Repository</h1>
          <p>Upload, inspect, and extract synthetic entities from investigation files.</p>
        </div>
      </header>

      <div
        className="dropzone"
        onClick={() => fileInputRef.current?.click()}
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => {
          e.preventDefault();
          if (e.dataTransfer.files?.[0]) handleUpload(e.dataTransfer.files[0]);
        }}
      >
        <Upload size={32} style={{ color: '#38bdf8', opacity: 0.8 }} />
        <h3 style={{ margin: '8px 0 2px' }}>
          {uploading ? 'Processing file upload…' : 'Click or Drag & Drop File Here to Ingest'}
        </h3>
        <p>Supports TXT, CSV, JSON, PDF, DOCX, and images (Max 10 MB)</p>
        <input
          ref={fileInputRef}
          type="file"
          style={{ display: 'none' }}
          onChange={(e) => {
            if (e.target.files?.[0]) handleUpload(e.target.files[0]);
          }}
        />
      </div>

      <article className="table">
        <div className="row head">
          <span>Filename / Storage</span>
          <span>Format & Language</span>
          <span>SHA-256 Checksum</span>
          <span>Action</span>
        </div>
        {docs.map((d) => (
          <div className="row" key={d.id}>
            <b>{d.filename}</b>
            <span>
              <Badge kind="neutral">{d.document_type}</Badge> {d.language}
            </span>
            <span><code>{d.checksum?.slice(0, 16)}...</code></span>
            <span>
              {['TXT', 'CSV', 'JSON'].includes(d.document_type) && (
                <button
                  className="btn-small btn-secondary"
                  onClick={() => handleProcess(d.id)}
                  disabled={!canUpload}
                >
                  Extract Entities
                </button>
              )}
              <button className="btn-small btn-secondary" onClick={() => inspectExtraction(d)}>
                Inspect extraction
              </button>
            </span>
          </div>
        ))}
        {!docs.length && <p className="empty">No documents in this case repository.</p>}
      </article>
      {!!selectedDocument && (
        <article className="table" style={{ marginTop: 18 }}>
          <div style={{ padding: '14px 16px' }}>
            <b>Extraction provenance: {selectedDocument}</b>
            <p className="muted">Source snippet, language, method, and confidence are shown for human verification.</p>
          </div>
          <div className="row head">
            <span>Entity</span><span>Confidence / Language</span><span>Method</span><span>Source text</span>
          </div>
          {extractedEntities.map((entity) => (
            <div className="row" key={entity.id}>
              <span><b>{entity.canonical_name}</b> <Badge kind="neutral">{entity.entity_type}</Badge></span>
              <span><Badge kind={confidenceKind(entity.confidence || 0)}>{Math.round((entity.confidence || 0) * 100)}%</Badge> {entity.language || 'en'}</span>
              <span>{entity.extraction_method || 'legacy record'}</span>
              <span title={entity.source_text_span}>{entity.source_text_span || 'No source span retained'}</span>
            </div>
          ))}
          {!extractedEntities.length && <p className="empty">No entities were extracted from this document.</p>}
        </article>
      )}
    </>
  );
}

// -------------------------------------------------------------
// REPORTS VIEW
// -------------------------------------------------------------
function ReportsView({
  caseId,
  token,
  reports,
  setReports,
  userRole,
  addToast,
}: {
  caseId: string;
  token: string;
  reports: Item[];
  setReports: (x: Item[]) => void;
  userRole: string;
  addToast: (msg: string, typ?: string) => void;
}) {
  const [generating, setGenerating] = useState(false);
  const canGenerate = ['ADMIN', 'SUPERVISOR', 'INVESTIGATOR', 'ANALYST'].includes(userRole);

  const createReport = async () => {
    if (!canGenerate) {
      addToast('Viewer role cannot generate new reports.', 'error');
      return;
    }
    setGenerating(true);
    try {
      const res = await api(`/cases/${caseId}/reports`, token, {
        method: 'POST',
        body: JSON.stringify({
          title: 'TriNetra Analytical Intelligence Briefing Dossier',
          format: 'HTML',
        }),
      });
      setReports([res, ...reports]);
      addToast('Analytical intelligence dossier generated.', 'success');
    } catch (e: any) {
      addToast(e.message, 'error');
    } finally {
      setGenerating(false);
    }
  };

  const openReport = async (id: string) => {
    try {
      const r = await fetch(`${API}/reports/${id}/download`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!r.ok) throw new Error('Failed to download report');
      const page = await r.text();
      const blob = new Blob([page], { type: 'text/html' });
      const url = URL.createObjectURL(blob);
      window.open(url, '_blank');
    } catch (e: any) {
      addToast(e.message, 'error');
    }
  };

  return (
    <>
      <header>
        <div>
          <p className="eyebrow">REPORTS & DOSSIERS</p>
          <h1>Evidence-Aware Analytical Dossiers</h1>
          <p>Generate comprehensive print-ready investigation briefings with responsible AI disclaimers.</p>
        </div>
        <button disabled={generating || !canGenerate} onClick={createReport}>
          {generating ? 'Compiling Dossier…' : 'Generate Analytical Dossier'}
        </button>
      </header>
      <Notice />
      <article className="table">
        <div className="row head">
          <span>Report Title</span>
          <span>Format</span>
          <span>Status</span>
          <span>Action</span>
        </div>
        {reports.map((r) => (
          <div className="row" key={r.id}>
            <b>{r.title}</b>
            <span>{r.format}</span>
            <span><Badge kind="green">{r.status}</Badge></span>
            <button className="btn-small" onClick={() => openReport(r.id)}>
              Open / Print Dossier
            </button>
          </div>
        ))}
        {!reports.length && (
          <p className="empty">No reports generated yet. Click above to generate an analytical dossier.</p>
        )}
      </article>
    </>
  );
}

// -------------------------------------------------------------
// AUDIT TRAIL VIEW (Admin only)
// -------------------------------------------------------------
function AuditView({ token, userRole, addToast }: { token: string; userRole: string; addToast: (msg: string, typ?: string) => void }) {
  const [logs, setLogs] = useState<Item[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (userRole !== 'ADMIN') return;
    setLoading(true);
    api('/audit-logs', token)
      .then(setLogs)
      .catch((e: any) => addToast(e.message, 'error'))
      .finally(() => setLoading(false));
  }, [token, userRole]);

  if (userRole !== 'ADMIN') {
    return (
      <>
        <header>
          <div>
            <p className="eyebrow">AUDIT TRAIL & LOGS</p>
            <h1>System Audit Activity</h1>
          </div>
        </header>
        <div className="notice warning">
          <AlertTriangle size={18} />
          <span>Access Restricted: Audit trail inspection requires the Administrator role. You are signed in as {userRole}.</span>
        </div>
      </>
    );
  }

  return (
    <>
      <header>
        <div>
          <p className="eyebrow">COMPLIANCE & INTEGRITY</p>
          <h1>System Audit Trail</h1>
          <p>Chronological log of user actions, logins, match decisions, report exports, and queries.</p>
        </div>
      </header>

      {loading ? (
        <div className="skeleton">Loading audit logs…</div>
      ) : (
        <article className="table">
          <div className="row head">
            <span>Timestamp</span>
            <span>Action & Resource</span>
            <span>User ID</span>
            <span>Resource ID</span>
          </div>
          {logs.map((l) => (
            <div className="row" key={l.id}>
              <span className="muted">{l.created_at?.replace('T', ' ').slice(0, 19)}</span>
              <span>
                <Badge kind={l.action.includes('FAIL') ? 'red' : 'neutral'}>{l.action}</Badge>{' '}
                {l.resource_type}
              </span>
              <span><code>{l.user_id?.slice(0, 12)}...</code></span>
              <span><code>{l.resource_id?.slice(0, 14)}...</code></span>
            </div>
          ))}
          {!logs.length && <p className="empty">No audit events recorded.</p>}
        </article>
      )}
    </>
  );
}

// -------------------------------------------------------------
// MAIN APP COMPONENT
// -------------------------------------------------------------
export function App() {
  const [auth, setAuth] = useState<any>(null);

  const [page, setPage] = useState('overview');
  const [casesList, setCasesList] = useState<Item[]>([]);
  const [activeCase, setActiveCase] = useState<Item | null>(null);
  const [showNewCaseModal, setShowNewCaseModal] = useState(false);

  const [graph, setGraph] = useState<Item>({});
  const [summary, setSummary] = useState<Item>({});
  const [entities, setEntities] = useState<Item[]>([]);
  const [docs, setDocs] = useState<Item[]>([]);
  const [alerts, setAlerts] = useState<Item[]>([]);
  const [gaps, setGaps] = useState<Item[]>([]);
  const [reports, setReports] = useState<Item[]>([]);
  const [selected, setSelected] = useState<Item | null>(null);

  const [toasts, setToasts] = useState<Array<{ id: string; msg: string; type: string }>>([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const addToast = (msg: string, type = 'info') => {
    const id = Math.random().toString(36).substring(2, 9);
    setToasts((prev) => [...prev, { id, msg, type }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 4000);
  };

  // Listen for unauthorized 401 events to auto logout
  useEffect(() => {
    const handleUnauth = () => {
      localStorage.removeItem('trinetra-auth');
      setAuth(null);
      addToast('Session expired. Please log in again.', 'error');
    };
    window.addEventListener('trinetra-unauthorized', handleUnauth);
    return () => window.removeEventListener('trinetra-unauthorized', handleUnauth);
  }, []);

  // Load cases list
  useEffect(() => {
    if (!auth?.access_token) return;
    api('/cases', auth.access_token)
      .then((cs: Item[]) => {
        setCasesList(cs);
        if (cs.length > 0 && !activeCase) {
          setActiveCase(cs[0]);
        }
      })
      .catch((e: any) => setError(e.message));
  }, [auth]);

  // Load active case scoped data
  useEffect(() => {
    if (!auth?.access_token || !activeCase?.id) return;
    const loadCaseData = async () => {
      setLoading(true);
      setError('');
      try {
        const [g, s, e, d, a, ga, r] = await Promise.all([
          api(`/cases/${activeCase.id}/graph`, auth.access_token),
          api(`/cases/${activeCase.id}/analytics/summary`, auth.access_token),
          api(`/cases/${activeCase.id}/entities`, auth.access_token),
          api(`/cases/${activeCase.id}/documents`, auth.access_token),
          api(`/cases/${activeCase.id}/alerts`, auth.access_token),
          api(`/cases/${activeCase.id}/data-gaps`, auth.access_token),
          api(`/cases/${activeCase.id}/reports`, auth.access_token),
        ]);
        setGraph(g);
        setSummary(s);
        setEntities(e);
        setDocs(d);
        setAlerts(a);
        setGaps(ga);
        setReports(r);
        setSelected(null);
      } catch (e: any) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    };
    loadCaseData();
  }, [auth, activeCase?.id]);

  if (!auth) {
    return (
      <Login
        onLogin={(x) => {
          setAuth(x);
        }}
      />
    );
  }

  const logout = () => {
    localStorage.removeItem('trinetra-auth');
    setAuth(null);
  };

  const handleCaseChange = (caseId: string) => {
    const found = casesList.find((c) => c.id === caseId);
    if (found) setActiveCase(found);
  };

  // Quick switch role demo helper
  const handleQuickRoleSwitch = async (email: string) => {
    try {
      const res = await api('/auth/login', undefined, {
        method: 'POST',
        body: JSON.stringify({ email, password: 'TriNetraDemo!2026' }),
      });
      setAuth(res);
      addToast(`Switched account to: ${res.user?.name} (${res.user?.role})`, 'success');
    } catch (e: any) {
      addToast(e.message, 'error');
    }
  };

  const canCreateCase = ['ADMIN', 'SUPERVISOR', 'INVESTIGATOR'].includes(auth.user?.role);

  return (
    <div className="app">
      <Nav page={page} setPage={setPage} user={auth.user} onLogout={logout} />

      <main className="content">
        <div className="top-bar">
          <div className="case-selector">
            <span className="muted" style={{ fontSize: '12px' }}>Case:</span>
            <select
              value={activeCase?.id || ''}
              onChange={(e) => handleCaseChange(e.target.value)}
              aria-label="Active Case Scope"
            >
              {casesList.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.case_number} — {c.title}
                </option>
              ))}
            </select>
            <button
              className="btn-secondary btn-small"
              disabled={!canCreateCase}
              onClick={() => setShowNewCaseModal(true)}
              title={!canCreateCase ? 'Viewer and Analyst roles cannot create cases' : 'Create new case'}
            >
              <Plus size={13} /> New Case
            </button>
          </div>

          <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
            <div className="role-switcher">
              <span>Demo Role:</span>
              <select
                value={auth.user?.email}
                onChange={(e) => handleQuickRoleSwitch(e.target.value)}
                aria-label="Quick Switch Demo Account"
              >
                {DEMO_ACCOUNTS.map((acc) => (
                  <option key={acc.email} value={acc.email}>
                    {acc.role} ({acc.name})
                  </option>
                ))}
              </select>
            </div>
            <div className="top-demo">
              <ShieldCheck size={13} />
              <span>DEMO DATA — SYNTHETIC ENVIRONMENT</span>
            </div>
          </div>
        </div>

        {error && <div className="error" role="alert">{error}</div>}

        {loading ? (
          <div className="skeleton" aria-label="Loading case data">
            Loading protected synthetic case intelligence records…
          </div>
        ) : (
          <>
            {page === 'overview' && (
              <Overview summary={summary} caseData={activeCase || {}} onPage={setPage} />
            )}
            {page === 'workspace' && (
              <Workspace
                caseData={activeCase || {}}
                graph={graph}
                selected={selected}
                setSelected={setSelected}
                docs={docs}
                token={auth.access_token}
                addToast={addToast}
              />
            )}
            {page === 'graph' && (
              <GraphView
                graph={graph}
                caseId={activeCase?.id || ''}
                token={auth.access_token}
                addToast={addToast}
              />
            )}
            {page === 'entities' && (
              <Entities
                entities={entities}
                onSelectEntity={(e) => {
                  setSelected(e);
                  setPage('workspace');
                }}
              />
            )}
            {page === 'matches' && (
              <Matches
                caseId={activeCase?.id || ''}
                entities={entities}
                token={auth.access_token}
                userRole={auth.user?.role}
                addToast={addToast}
              />
            )}
            {page === 'timeline' && (
              <TimelineView
                caseId={activeCase?.id || ''}
                token={auth.access_token}
                addToast={addToast}
              />
            )}
            {page === 'analytics' && <Analytics summary={summary} />}
            {page === 'alerts' && <Alerts alerts={alerts} gaps={gaps} />}
            {page === 'copilot' && (
              <Copilot caseId={activeCase?.id || ''} token={auth.access_token} />
            )}
            {page === 'documents' && (
              <DocumentsView
                caseId={activeCase?.id || ''}
                token={auth.access_token}
                docs={docs}
                setDocs={setDocs}
                userRole={auth.user?.role}
                addToast={addToast}
              />
            )}
            {page === 'reports' && (
              <ReportsView
                caseId={activeCase?.id || ''}
                token={auth.access_token}
                reports={reports}
                setReports={setReports}
                userRole={auth.user?.role}
                addToast={addToast}
              />
            )}
            {page === 'audit' && (
              <AuditView
                token={auth.access_token}
                userRole={auth.user?.role}
                addToast={addToast}
              />
            )}
          </>
        )}
      </main>

      {showNewCaseModal && (
        <NewCaseModal
          token={auth.access_token}
          onClose={() => setShowNewCaseModal(false)}
          onCreated={(newCase) => {
            setCasesList([newCase, ...casesList]);
            setActiveCase(newCase);
          }}
          addToast={addToast}
        />
      )}

      <div className="toast-container" aria-live="assertive">
        {toasts.map((t) => (
          <div key={t.id} className={`toast ${t.type}`}>
            {t.msg}
          </div>
        ))}
      </div>
    </div>
  );
}

const rootEl = document.getElementById('root');
if (rootEl) {
  createRoot(rootEl).render(<App />);
}
