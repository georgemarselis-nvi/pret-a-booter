#!/usr/bin/env python3
"""
generate_schema_hierarchy.py

Generates a complete OpenLDAP schema inheritance hierarchy SVG.
- Parses all .schema files from SCHEMA_DIR
- Resolves full MUST/MAY attribute inheritance per objectClass
- Renders O'Reilly UML box notation
- Left-to-right layout, top node at upper left
- Inherited attributes marked with source objectClass

Usage:
    python3 generate_schema_hierarchy.py
    # Output: openldap_schema_hierarchy.svg

Requirements: Python 3 stdlib only (json, html, re, collections)

Author: generated for pret-a-booter / NVI LDAP infrastructure
"""

import re
import os
import json
import html
from collections import deque

# ── Config ────────────────────────────────────────────────────────────────────
SCHEMA_DIR = '/etc/ldap/schema'
OUTPUT_FILE = 'openldap_schema_hierarchy.svg'

SCHEMA_FILES = [
    'core', 'cosine', 'inetorgperson', 'collective', 'corba', 'dsee',
    'duaconf', 'dyngroup', 'java', 'misc', 'msuser', 'namedobject',
    'nis', 'openldap', 'pmi'
]

ROW_H    = 15
HEADER_H = 44
SEP_H    = 8
BOX_W    = 250
GAP_X    = 120   # horizontal gap between depth levels
GAP_Y    = 20    # vertical gap between sibling boxes
MARGIN   = 60
TITLE_H  = 70

KIND_COLOR = {
    'STRUCTURAL': '#1a4a7a',
    'AUXILIARY':  '#5a1a7a',
    'ABSTRACT':   '#1a5a2a',
}

# ── Schema parser ─────────────────────────────────────────────────────────────

def parse_schema_file(path):
    """Parse a .schema file and return (ocs, attrs) lists."""
    with open(path) as f:
        content = f.read()
    # Strip comments
    content = re.sub(r'#[^\n]*', '', content)
    # Normalize continuation lines
    content = re.sub(r'\n[\t ]+', ' ', content)

    ocs   = []
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
                if content[i] == '(':
                    depth += 1
                elif content[i] == ')':
                    depth -= 1
                    if depth == 0:
                        break
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
        attr['sup']        = sup_m.group(1)             if sup_m    else ''
        attr['syntax']     = syntax_m.group(1).rstrip(')')  if syntax_m else ''
        attr['single']     = bool(re.search(r'SINGLE-VALUE', raw, re.IGNORECASE))
        attr['collective'] = bool(re.search(r'COLLECTIVE',   raw, re.IGNORECASE))
        attr['desc']       = desc_m.group(1)             if desc_m   else ''
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

# top is a system OC not in schema files
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

# Build children map
children_map = {name: [] for name in all_ocs}
for name, oc in all_ocs.items():
    sup = (oc.get('sup') or '').lower().strip()
    if sup and sup in all_ocs and sup != name:
        children_map[sup].append(name)
    elif name != 'top' and (not sup or sup not in all_ocs):
        children_map['top'].append(name)
for name in children_map:
    children_map[name] = sorted(set(children_map[name]))

# BFS order for rendering
bfs_order = []
visited_bfs = set()
queue = deque(['top'])
while queue:
    name = queue.popleft()
    if name in visited_bfs:
        continue
    visited_bfs.add(name)
    bfs_order.append(name)
    for child in children_map.get(name, []):
        queue.append(child)

# Assign positions: each node x = depth*(BOX_W+GAP_X)+MARGIN
# y: top-aligned to first child; leaves get sequential y slots
node_pos = {}

def assign_pos(name, x, y_start, vis=None):
    if vis is None:
        vis = set()
    if name in vis:
        return y_start
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
    # top-align parent with its first child
    node_pos[name] = (x, node_pos[kids[0]][1])
    return y_cursor

assign_pos('top', MARGIN, TITLE_H + MARGIN)

total_w = int(max(x + BOX_W for x, y in node_pos.values())) + MARGIN
total_h = int(max(y + box_height(n) for n, (x, y) in node_pos.items())) + MARGIN


# ── SVG rendering ─────────────────────────────────────────────────────────────

def e(s):
    return html.escape(str(s) if s else '')

def render_box(name):
    oc        = all_ocs.get(name, {})
    must, may = get_all_attrs_for_oc(name)
    h         = box_height(name)
    x, y      = node_pos[name]
    kc        = KIND_COLOR.get(oc.get('kind', ''), '#444')
    cx        = x + BOX_W // 2
    p         = [f'<g id="oc_{e(name)}">']

    p.append(f'<rect x="{x}" y="{y}" width="{BOX_W}" height="{h}" rx="3" fill="white" stroke="#555" stroke-width="1.5"/>')
    p.append(f'<rect x="{x}" y="{y}" width="{BOX_W}" height="{HEADER_H}" rx="3" fill="{kc}"/>')
    p.append(f'<rect x="{x}" y="{y+HEADER_H-6}" width="{BOX_W}" height="6" fill="{kc}"/>')
    p.append(f'<text x="{cx}" y="{y+16}" text-anchor="middle" font-family="monospace" font-size="12" font-weight="bold" fill="white">{e(oc.get("name", name))}</text>')
    p.append(f'<text x="{cx}" y="{y+28}" text-anchor="middle" font-family="monospace" font-size="9"  fill="#cdf">{e(oc.get("kind",""))}</text>')
    p.append(f'<text x="{cx}" y="{y+39}" text-anchor="middle" font-family="monospace" font-size="8"  fill="#9ac">{e(oc.get("schema",""))} · {e(oc.get("oid",""))}</text>')

    ry = y + HEADER_H + 6
    for attr, src in must:
        inherited = src != name
        col = '#880000' if not inherited else '#bb4400'
        wt  = 'bold'   if not inherited else 'normal'
        p.append(f'<text x="{x+5}" y="{ry+11}" font-family="monospace" font-size="9" fill="{col}" font-weight="{wt}">■ {e(attr)}</text>')
        if inherited:
            p.append(f'<text x="{x+BOX_W-3}" y="{ry+11}" text-anchor="end" font-family="monospace" font-size="7" fill="#999">↑{e(src)}</text>')
        ry += ROW_H
    if not must:
        p.append(f'<text x="{x+5}" y="{ry+11}" font-family="monospace" font-size="8" fill="#bbb" font-style="italic">(no MUST)</text>')
        ry += ROW_H

    ry += 4
    p.append(f'<line x1="{x}" y1="{ry}" x2="{x+BOX_W}" y2="{ry}" stroke="#aaa" stroke-width="1" stroke-dasharray="5,3"/>')
    ry += SEP_H

    for attr, src in may:
        inherited = src != name
        col = '#111' if not inherited else '#666'
        p.append(f'<text x="{x+5}" y="{ry+11}" font-family="monospace" font-size="9" fill="{col}">○ {e(attr)}</text>')
        if inherited:
            p.append(f'<text x="{x+BOX_W-3}" y="{ry+11}" text-anchor="end" font-family="monospace" font-size="7" fill="#bbb">↑{e(src)}</text>')
        ry += ROW_H
    if not may:
        p.append(f'<text x="{x+5}" y="{ry+11}" font-family="monospace" font-size="8" fill="#bbb" font-style="italic">(no MAY)</text>')

    p.append('</g>')
    return '\n'.join(p)


def render_arrows():
    parts = []
    for name in bfs_order:
        sup = (all_ocs.get(name, {}).get('sup') or '').lower().strip()
        if sup and sup in node_pos and sup != name:
            px, py = node_pos[sup]
            ph = box_height(sup)
            cx2, cy2 = node_pos[name]
            ch = box_height(name)
            x1, y1 = px + BOX_W, py + ph // 2
            x2, y2 = cx2,        cy2 + ch // 2
            mx = (x1 + x2) // 2
            parts.append(f'<path d="M{x1},{y1} C{mx},{y1} {mx},{y2} {x2},{y2}" fill="none" stroke="#999" stroke-width="1.5" stroke-dasharray="7,4" marker-end="url(#arr)"/>')
    return parts


# ── Assemble SVG ──────────────────────────────────────────────────────────────

svg = ['<?xml version="1.0" encoding="UTF-8"?>']
svg.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{total_w}" height="{total_h}" viewBox="0 0 {total_w} {total_h}">')
svg.append('<defs><marker id="arr" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0 L0,6 L8,3 z" fill="#888"/></marker></defs>')
svg.append(f'<rect width="{total_w}" height="{total_h}" fill="#e8e8e8"/>')

# Title
svg.append(f'<rect width="{total_w}" height="{TITLE_H}" fill="#111"/>')
svg.append(f'<text x="{MARGIN}" y="28" font-family="monospace" font-size="20" font-weight="bold" fill="#4af">OpenLDAP Default Schema — Complete Inheritance Hierarchy</text>')
svg.append(f'<text x="{MARGIN}" y="45" font-family="monospace" font-size="11" fill="#888">'
           f'{len(bfs_order)} objectClasses · all MUST/MAY shown · inherited attrs marked ↑parent · parsed from slapd 2.6.x · left→right by depth · top-aligned'
           f'</text>')

# Legend
lx, ly = MARGIN, 52
for kind, col in KIND_COLOR.items():
    svg.append(f'<rect x="{lx}" y="{ly}" width="10" height="10" fill="{col}"/>')
    svg.append(f'<text x="{lx+13}" y="{ly+10}" font-family="monospace" font-size="10" fill="#ddd">{kind}</text>')
    lx += 120
svg.append(f'<text x="{lx+5}"   y="{ly+10}" font-family="monospace" font-size="10" fill="#f88">■ MUST</text>')
svg.append(f'<text x="{lx+65}"  y="{ly+10}" font-family="monospace" font-size="10" fill="#ddd">○ MAY</text>')
svg.append(f'<text x="{lx+115}" y="{ly+10}" font-family="monospace" font-size="10" fill="#aaa">↑inherited from parent</text>')

svg.extend(render_arrows())
for name in bfs_order:
    svg.append(render_box(name))

svg.append('</svg>')

with open(OUTPUT_FILE, 'w') as f:
    f.write('\n'.join(svg))

print(f"Written {OUTPUT_FILE}: {total_w}x{total_h}px, {len(bfs_order)} objectClasses")
