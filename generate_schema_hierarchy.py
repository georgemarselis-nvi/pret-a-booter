#!/usr/bin/env python3
"""
generate_schema_hierarchy.py

Generates a complete OpenLDAP schema inheritance hierarchy SVG.
- Parses all .schema files from SCHEMA_DIR
- Resolves full MUST/MAY attribute inheritance per objectClass
- Renders O'Reilly UML box notation
- Left-to-right layout, top node at upper left
- Inherited attributes marked with source objectClass
- Print-ready SVG with physical dimensions at specified DPI
- Optional black-and-white output for printing

Usage:
    python3 generate_schema_hierarchy.py
    python3 generate_schema_hierarchy.py --dpi 300
    python3 generate_schema_hierarchy.py --dpi 300 --paper A0 --landscape
    python3 generate_schema_hierarchy.py --dpi 300 --bw
    python3 generate_schema_hierarchy.py --dpi 300 --paper custom --width-mm 2000 --height-mm 1200

    --dpi        Output DPI (default: 300)
    --paper      Paper size: A0, A1, A2, A3, A4, custom, auto (default: auto = fit content)
    --landscape  Landscape orientation
    --width-mm   Custom paper width in mm (requires --paper custom)
    --height-mm  Custom paper height in mm (requires --paper custom)
    --bw         Black and white output
    --output     Output filename (default: openldap_schema_hierarchy.svg)

    Standard large-format paper sizes (mm):
      A0: 841x1189   A1: 594x841   A2: 420x594

Requirements: Python 3 stdlib only

Author: generated for pret-a-booter / NVI LDAP infrastructure
"""

import re
import os
import json
import html
import argparse
from collections import deque

# ── CLI ───────────────────────────────────────────────────────────────────────
parser = argparse.ArgumentParser()
parser.add_argument('--dpi',       type=int,   default=300)
parser.add_argument('--paper',     type=str,   default='auto',
                    choices=['auto','A0','A1','A2','A3','A4','custom'])
parser.add_argument('--landscape', action='store_true')
parser.add_argument('--width-mm',  type=float, default=None)
parser.add_argument('--height-mm', type=float, default=None)
parser.add_argument('--bw',        action='store_true', help='Black and white output')
parser.add_argument('--output',    type=str,   default='openldap_schema_hierarchy.svg')
args = parser.parse_args()

PAPER_SIZES_MM = {
    'A0': (841, 1189), 'A1': (594, 841),
    'A2': (420, 594),  'A3': (297, 420), 'A4': (210, 297),
}

# ── Colors ────────────────────────────────────────────────────────────────────
if args.bw:
    KIND_COLOR     = {'STRUCTURAL': '#000000', 'AUXILIARY': '#555555', 'ABSTRACT': '#aaaaaa'}
    C_CANVAS_BG    = '#ffffff'
    C_TITLE_BG     = '#000000'
    C_TITLE_FG     = '#ffffff'
    C_SUBTITLE_FG  = '#666666'
    C_HEADER_FG    = '#ffffff'
    C_KIND_FG      = '#cccccc'
    C_OID_FG       = '#cccccc'
    C_BOX_BG       = '#ffffff'
    C_BOX_STROKE   = '#000000'
    C_MUST         = '#000000'
    C_MUST_INH     = '#444444'
    C_MAY          = '#000000'
    C_MAY_INH      = '#666666'
    C_INHERITED    = '#888888'
    C_NONE         = '#aaaaaa'
    C_SEP          = '#666666'
    C_ARROW        = '#333333'
    C_ARROW_HEAD   = '#333333'
    C_LEGEND_FG    = '#ffffff'
    C_LEGEND_MUST  = '#ffffff'
    C_LEGEND_MAY   = '#ffffff'
    C_LEGEND_INH   = '#cccccc'
else:
    KIND_COLOR     = {'STRUCTURAL': '#1a4a7a', 'AUXILIARY': '#5a1a7a', 'ABSTRACT': '#1a5a2a'}
    C_CANVAS_BG    = '#e8e8e8'
    C_TITLE_BG     = '#111111'
    C_TITLE_FG     = '#4af'
    C_SUBTITLE_FG  = '#888888'
    C_HEADER_FG    = '#ffffff'
    C_KIND_FG      = '#cdf'
    C_OID_FG       = '#9ac'
    C_BOX_BG       = '#ffffff'
    C_BOX_STROKE   = '#555555'
    C_MUST         = '#880000'
    C_MUST_INH     = '#bb4400'
    C_MAY          = '#111111'
    C_MAY_INH      = '#666666'
    C_INHERITED    = '#999999'
    C_NONE         = '#bbbbbb'
    C_SEP          = '#aaaaaa'
    C_ARROW        = '#999999'
    C_ARROW_HEAD   = '#888888'
    C_LEGEND_FG    = '#dddddd'
    C_LEGEND_MUST  = '#f88'
    C_LEGEND_MAY   = '#dddddd'
    C_LEGEND_INH   = '#aaaaaa'

# ── Config ────────────────────────────────────────────────────────────────────
SCHEMA_DIR  = '/etc/ldap/schema'
OUTPUT_FILE = args.output
DPI         = args.dpi

SCHEMA_FILES = [
    'core', 'cosine', 'inetorgperson', 'collective', 'corba', 'dsee',
    'duaconf', 'dyngroup', 'java', 'misc', 'msuser', 'namedobject',
    'nis', 'openldap', 'pmi'
]

ROW_H    = 15
HEADER_H = 44
SEP_H    = 8
BOX_W    = 250
GAP_X    = 120
GAP_Y    = 20
MARGIN   = 60
TITLE_H  = 70

# ── Schema parser ─────────────────────────────────────────────────────────────

def parse_schema_file(path):
    with open(path) as f:
        content = f.read()
    content = re.sub(r'#[^\n]*', '', content)
    content = re.sub(r'\n[\t ]+', ' ', content)

    ocs = []
    attrs = []

    def extract_blocks(keyword):
        pos = 0
        while True:
            m = re.search(rf'{keyword}\s*\(', content[pos:], re.IGNORECASE)
            if not m:
                break
            start = pos + m.end() - 1
            depth = 0
            i = start
            while i < len(content):
                if content[i] == '(':   depth += 1
                elif content[i] == ')':
                    depth -= 1
                    if depth == 0: break
                i += 1
            yield content[start+1:i].strip()
            pos = pos + m.start() + 1

    for raw in extract_blocks('objectclass'):
        oc = {}
        oid_m = re.match(r'(\S+)', raw)
        oc['oid'] = oid_m.group(1) if oid_m else ''
        name_m = re.search(r"NAME\s*\(\s*'([^']+)'", raw, re.IGNORECASE) or \
                 re.search(r"NAME\s+'([^']+)'",       raw, re.IGNORECASE)
        oc['name'] = name_m.group(1) if name_m else ''
        if not oc['name']:
            continue
        sup_m = re.search(r'SUP\s+(\S+)', raw, re.IGNORECASE)
        oc['sup'] = sup_m.group(1) if sup_m else ''
        oc['kind'] = 'STRUCTURAL'
        for kind in ('STRUCTURAL', 'AUXILIARY', 'ABSTRACT'):
            if re.search(r'\b' + kind + r'\b', raw, re.IGNORECASE):
                oc['kind'] = kind
                break
        must_m = re.search(r'MUST\s+\(([^)]+)\)', raw, re.IGNORECASE)
        if must_m:
            oc['must'] = [x.strip() for x in re.split(r'\$', must_m.group(1)) if x.strip()]
        else:
            must_m = re.search(r'MUST\s+(\S+)', raw, re.IGNORECASE)
            oc['must'] = [must_m.group(1)] if must_m else []
        may_m = re.search(r'MAY\s+\(([^)]+)\)', raw, re.IGNORECASE)
        if may_m:
            oc['may'] = [x.strip() for x in re.split(r'\$', may_m.group(1)) if x.strip()]
        else:
            may_m = re.search(r'MAY\s+(\S+)', raw, re.IGNORECASE)
            oc['may'] = [may_m.group(1)] if may_m else []
        desc_m = re.search(r"DESC\s+'([^']+)'", raw, re.IGNORECASE)
        oc['desc'] = desc_m.group(1) if desc_m else ''
        ocs.append(oc)

    for raw in extract_blocks('attributetype'):
        attr = {}
        oid_m = re.match(r'(\S+)', raw)
        attr['oid'] = oid_m.group(1) if oid_m else ''
        name_m = re.search(r"NAME\s*\(\s*'([^']+)'", raw, re.IGNORECASE) or \
                 re.search(r"NAME\s+'([^']+)'",       raw, re.IGNORECASE)
        attr['name'] = name_m.group(1) if name_m else ''
        if not attr['name']:
            continue
        sup_m    = re.search(r'SUP\s+(\S+)',    raw, re.IGNORECASE)
        syntax_m = re.search(r'SYNTAX\s+(\S+)', raw, re.IGNORECASE)
        desc_m   = re.search(r"DESC\s+'([^']+)'", raw, re.IGNORECASE)
        attr['sup']        = sup_m.group(1)                  if sup_m    else ''
        attr['syntax']     = syntax_m.group(1).rstrip(')')   if syntax_m else ''
        attr['single']     = bool(re.search(r'SINGLE-VALUE', raw, re.IGNORECASE))
        attr['collective'] = bool(re.search(r'COLLECTIVE',   raw, re.IGNORECASE))
        attr['desc']       = desc_m.group(1)                 if desc_m   else ''
        attrs.append(attr)

    return ocs, attrs

# ── Build global lookups ──────────────────────────────────────────────────────

all_ocs          = {}
all_attrs_lookup = {}

for schema_name in SCHEMA_FILES:
    path = os.path.join(SCHEMA_DIR, f'{schema_name}.schema')
    if not os.path.exists(path):
        continue
    ocs, attrs = parse_schema_file(path)
    for a in attrs:
        all_attrs_lookup[a['name'].lower()] = {**a, 'schema': schema_name}
    for oc in ocs:
        all_ocs[oc['name'].lower()] = {**oc, 'schema': schema_name}

all_ocs['top'] = {
    'name': 'top', 'oid': '2.5.6.0',
    'desc': 'top of superclass chain',
    'sup': '', 'kind': 'ABSTRACT',
    'must': ['objectClass'], 'may': [],
    'schema': 'core'
}

# ── Attribute inheritance ─────────────────────────────────────────────────────

def get_ancestor_chain(oc_name):
    chain, visited = [], set()
    name = oc_name.lower()
    while name and name not in visited:
        visited.add(name)
        chain.insert(0, name)
        oc  = all_ocs.get(name, {})
        sup = (oc.get('sup') or '').lower().strip()
        if not sup or sup == name or sup == 'top':
            if name != 'top':
                chain.insert(0, 'top')
            break
        name = sup
    return chain

def get_all_attrs_for_oc(oc_name):
    must, may, seen = [], [], set()
    for name in get_ancestor_chain(oc_name):
        oc = all_ocs.get(name, {})
        for a in oc.get('must', []):
            if a.lower() not in seen:
                must.append((a, name)); seen.add(a.lower())
        for a in oc.get('may', []):
            if a.lower() not in seen:
                may.append((a, name)); seen.add(a.lower())
    return must, may

# ── Layout ────────────────────────────────────────────────────────────────────

def box_height(oc_name):
    must, may = get_all_attrs_for_oc(oc_name)
    return HEADER_H + SEP_H + max(len(must), 1)*ROW_H + SEP_H + max(len(may), 1)*ROW_H + 8

children_map = {name: [] for name in all_ocs}
for name, oc in all_ocs.items():
    sup = (oc.get('sup') or '').lower().strip()
    if sup and sup in all_ocs and sup != name:
        children_map[sup].append(name)
    elif name != 'top' and (not sup or sup not in all_ocs):
        children_map['top'].append(name)
for name in children_map:
    children_map[name] = sorted(set(children_map[name]))

bfs_order = []
visited_bfs = set()
from collections import deque
queue = deque(['top'])
while queue:
    name = queue.popleft()
    if name in visited_bfs: continue
    visited_bfs.add(name)
    bfs_order.append(name)
    for child in children_map.get(name, []):
        queue.append(child)

node_pos = {}

def assign_pos(name, x, y_start, vis=None):
    if vis is None: vis = set()
    if name in vis: return y_start
    vis.add(name)
    h    = box_height(name)
    kids = children_map.get(name, [])
    if not kids:
        node_pos[name] = (x, y_start)
        return y_start + h + GAP_Y
    child_x  = x + BOX_W + GAP_X
    y_cursor = y_start
    for kid in kids:
        y_cursor = assign_pos(kid, child_x, y_cursor, vis)
    node_pos[name] = (x, node_pos[kids[0]][1])
    return y_cursor

assign_pos('top', MARGIN, TITLE_H + MARGIN)

total_w = int(max(x + BOX_W for x, y in node_pos.values())) + MARGIN
total_h = int(max(y + box_height(n) for n, (x, y) in node_pos.items())) + MARGIN

# ── SVG rendering ─────────────────────────────────────────────────────────────

def e(s): return html.escape(str(s) if s else '')

def render_box(name):
    oc        = all_ocs.get(name, {})
    must, may = get_all_attrs_for_oc(name)
    h         = box_height(name)
    x, y      = node_pos[name]
    kc        = KIND_COLOR.get(oc.get('kind', ''), '#444444')
    cx        = x + BOX_W // 2
    p         = [f'<g id="oc_{e(name)}">']

    p.append(f'<rect x="{x}" y="{y}" width="{BOX_W}" height="{h}" rx="3" fill="{C_BOX_BG}" stroke="{C_BOX_STROKE}" stroke-width="1.5"/>')
    p.append(f'<rect x="{x}" y="{y}" width="{BOX_W}" height="{HEADER_H}" rx="3" fill="{kc}"/>')
    p.append(f'<rect x="{x}" y="{y+HEADER_H-6}" width="{BOX_W}" height="6" fill="{kc}"/>')
    p.append(f'<text x="{cx}" y="{y+16}" text-anchor="middle" font-family="monospace" font-size="12" font-weight="bold" fill="{C_HEADER_FG}">{e(oc.get("name", name))}</text>')
    p.append(f'<text x="{cx}" y="{y+28}" text-anchor="middle" font-family="monospace" font-size="9"  fill="{C_KIND_FG}">{e(oc.get("kind",""))}</text>')
    p.append(f'<text x="{cx}" y="{y+39}" text-anchor="middle" font-family="monospace" font-size="8"  fill="{C_OID_FG}">{e(oc.get("schema",""))} · {e(oc.get("oid",""))}</text>')

    ry = y + HEADER_H + 6
    for attr, src in must:
        inherited = src != name
        col = C_MUST_INH if inherited else C_MUST
        wt  = 'normal'  if inherited else 'bold'
        p.append(f'<text x="{x+5}" y="{ry+11}" font-family="monospace" font-size="9" fill="{col}" font-weight="{wt}">&#x25A0; {e(attr)}</text>')
        if inherited:
            p.append(f'<text x="{x+BOX_W-3}" y="{ry+11}" text-anchor="end" font-family="monospace" font-size="7" fill="{C_INHERITED}">&#x2191;{e(src)}</text>')
        ry += ROW_H
    if not must:
        p.append(f'<text x="{x+5}" y="{ry+11}" font-family="monospace" font-size="8" fill="{C_NONE}" font-style="italic">(no MUST)</text>')
        ry += ROW_H

    ry += 4
    p.append(f'<line x1="{x}" y1="{ry}" x2="{x+BOX_W}" y2="{ry}" stroke="{C_SEP}" stroke-width="1" stroke-dasharray="5,3"/>')
    ry += SEP_H

    for attr, src in may:
        inherited = src != name
        col = C_MAY_INH if inherited else C_MAY
        p.append(f'<text x="{x+5}" y="{ry+11}" font-family="monospace" font-size="9" fill="{col}">&#x25CB; {e(attr)}</text>')
        if inherited:
            p.append(f'<text x="{x+BOX_W-3}" y="{ry+11}" text-anchor="end" font-family="monospace" font-size="7" fill="{C_NONE}">&#x2191;{e(src)}</text>')
        ry += ROW_H
    if not may:
        p.append(f'<text x="{x+5}" y="{ry+11}" font-family="monospace" font-size="8" fill="{C_NONE}" font-style="italic">(no MAY)</text>')

    p.append('</g>')
    return '\n'.join(p)


def render_arrows():
    parts = []
    for name in bfs_order:
        sup = (all_ocs.get(name, {}).get('sup') or '').lower().strip()
        if sup and sup in node_pos and sup != name:
            px, py = node_pos[sup]
            ph     = box_height(sup)
            cx2, cy2 = node_pos[name]
            ch     = box_height(name)
            x1, y1 = px + BOX_W, py + ph // 2
            x2, y2 = cx2,        cy2 + ch // 2
            mx     = (x1 + x2) // 2
            parts.append(f'<path d="M{x1},{y1} C{mx},{y1} {mx},{y2} {x2},{y2}" fill="none" stroke="{C_ARROW}" stroke-width="1.5" stroke-dasharray="7,4" marker-end="url(#arr)"/>')
    return parts

# ── Physical dimensions ───────────────────────────────────────────────────────
px_per_mm = DPI / 25.4
w_mm = total_w / px_per_mm
h_mm = total_h / px_per_mm

if args.paper != 'auto':
    if args.paper == 'custom':
        paper_w_mm = args.width_mm or w_mm
        paper_h_mm = args.height_mm or h_mm
    else:
        pw, ph = PAPER_SIZES_MM[args.paper]
        paper_w_mm, paper_h_mm = (ph, pw) if args.landscape else (pw, ph)
    scale_fit  = min(paper_w_mm / w_mm, paper_h_mm / h_mm)
    w_mm       = paper_w_mm
    h_mm       = paper_h_mm
    vb_w       = int(total_w / scale_fit)
    vb_h       = int(total_h / scale_fit)
    viewbox    = f'0 0 {vb_w} {vb_h}'
else:
    viewbox = f'0 0 {total_w} {total_h}'

# ── Assemble SVG ──────────────────────────────────────────────────────────────
svg = ['<?xml version="1.0" encoding="UTF-8"?>']
svg.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{w_mm:.2f}mm" height="{h_mm:.2f}mm" viewBox="{viewbox}">')
svg.append(f'<defs><marker id="arr" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0 L0,6 L8,3 z" fill="{C_ARROW_HEAD}"/></marker></defs>')
svg.append(f'<rect width="{total_w}" height="{total_h}" fill="{C_CANVAS_BG}"/>')

# Title
svg.append(f'<rect width="{total_w}" height="{TITLE_H}" fill="{C_TITLE_BG}"/>')
svg.append(f'<text x="{MARGIN}" y="28" font-family="monospace" font-size="20" font-weight="bold" fill="{C_TITLE_FG}">OpenLDAP Default Schema &#x2014; Complete Inheritance Hierarchy</text>')
svg.append(f'<text x="{MARGIN}" y="45" font-family="monospace" font-size="11" fill="{C_SUBTITLE_FG}">'
           f'{len(bfs_order)} objectClasses &#xB7; all MUST/MAY shown &#xB7; inherited attrs marked &#x2191;parent &#xB7; parsed from slapd 2.6.x &#xB7; left&#x2192;right by depth'
           f'</text>')

# Legend
lx, ly = MARGIN, 52
for kind, col in KIND_COLOR.items():
    svg.append(f'<rect x="{lx}" y="{ly}" width="10" height="10" fill="{col}"/>')
    svg.append(f'<text x="{lx+13}" y="{ly+10}" font-family="monospace" font-size="10" fill="{C_LEGEND_FG}">{kind}</text>')
    lx += 120
svg.append(f'<text x="{lx+5}"   y="{ly+10}" font-family="monospace" font-size="10" fill="{C_LEGEND_MUST}">&#x25A0; MUST</text>')
svg.append(f'<text x="{lx+65}"  y="{ly+10}" font-family="monospace" font-size="10" fill="{C_LEGEND_MAY}">&#x25CB; MAY</text>')
svg.append(f'<text x="{lx+115}" y="{ly+10}" font-family="monospace" font-size="10" fill="{C_LEGEND_INH}">&#x2191;inherited from parent</text>')

svg.extend(render_arrows())
for name in bfs_order:
    svg.append(render_box(name))

svg.append('</svg>')

with open(OUTPUT_FILE, 'w') as f:
    f.write('\n'.join(svg))

print(f"Written {OUTPUT_FILE}: {total_w}x{total_h}px ({w_mm:.1f}x{h_mm:.1f}mm at {DPI}dpi), {len(bfs_order)} objectClasses, bw={args.bw}")
