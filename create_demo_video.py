#!/usr/bin/env python3
"""Generate a demo video showing the GraphHacks dashboard."""
from __future__ import annotations

import subprocess, sys, time, os, json
import requests
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch
import imageio

HOST = "127.0.0.1"
PORT = 8000
BASE_URL = f"http://{HOST}:{PORT}"
VIDEO_PATH = os.path.join(os.path.dirname(__file__), "static", "demo_video.mp4")
FPS = 24
FRAME_W, FRAME_H = 1600, 900
DPI = 100

COLORS = {
    "Person": "#00aaff", "Team": "#00ff88", "Project": "#ff8800",
    "System": "#aa00ff", "Document": "#ffd700", "Decision": "#ff69b4",
    "Meeting": "#98fb98", "Ticket": "#ffa07a", "Skill": "#87ceeb",
    "Concept": "#dda0dd", "Conversation": "#98fb98", "Memory": "#f0e68c",
}


def start_server() -> subprocess.Popen:
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "api:app", "--host", HOST, "--port", str(PORT)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    for _ in range(30):
        try:
            r = requests.get(f"{BASE_URL}/api/status", timeout=1)
            if r.status_code == 200:
                return proc
        except Exception:
            pass
        time.sleep(0.5)
    print("Warning: server may not be ready")
    return proc


def stop_server(proc: subprocess.Popen):
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except Exception:
        proc.kill()


def fetch_graph_data() -> dict:
    return requests.get(f"{BASE_URL}/api/graph_data", timeout=5).json()


def fetch_status() -> dict:
    return requests.get(f"{BASE_URL}/api/status", timeout=5).json()


def ask_question(question: str) -> dict:
    return requests.post(f"{BASE_URL}/api/ask", json={"question": question}, timeout=10).json()


def draw_dashboard_frame(frame_idx, graph_data=None, status_data=None,
                          qa_result=None, title="GraphHacks Dashboard",
                          subtitle="", phase="intro"):
    fig, ax = plt.subplots(figsize=(FRAME_W/DPI, FRAME_H/DPI), dpi=DPI)
    fig.patch.set_facecolor("#0a0a0a")
    ax.set_facecolor("#0a0a0a")
    ax.set_xlim(0, FRAME_W)
    ax.set_ylim(0, FRAME_H)
    ax.axis("off")

    # Header
    ax.text(30, FRAME_H - 30, "GraphHacks", fontsize=28, fontweight="bold", color="#00ff88")
    ax.text(30, FRAME_H - 55, "Agent with a Graph Context Layer", fontsize=14, color="#888")
    ax.text(30, FRAME_H - 75, title, fontsize=18, color="#e0e0e0")
    if subtitle:
        ax.text(30, FRAME_H - 95, subtitle, fontsize=12, color="#aaa")

    # Left sidebar - status boxes
    sidebar_x = 25
    sidebar_y = FRAME_H - 130
    stat_boxes = [("Nodes", "49"), ("Edges", "58"), ("Backend", "InMemory")]
    if status_data:
        snap = status_data.get("snapshot", {})
        stat_boxes = [
            ("Nodes", str(snap.get("node_count", 0))),
            ("Edges", str(snap.get("edge_count", 0))),
            ("Backend", status_data.get("backend", "N/A")),
        ]

    for i, (label, value) in enumerate(stat_boxes):
        y = sidebar_y - i * 55
        box = FancyBboxPatch((sidebar_x, y-22), 200, 44, boxstyle="round,pad=8",
                             linewidth=1, edgecolor="#333", facecolor="#151525")
        ax.add_patch(box)
        ax.text(sidebar_x + 10, y + 12, label, fontsize=10, color="#888")
        ax.text(sidebar_x + 10, y - 10, value, fontsize=16, fontweight="bold", color="#00aaff")

    if status_data and "snapshot" in status_data:
        labels_count = status_data["snapshot"].get("label_counts", {})
        lb_y = sidebar_y - len(stat_boxes) * 55 - 30
        ax.text(sidebar_x, lb_y, "Labels:", fontsize=11, color="#ff8800")
        for j, (label, count) in enumerate(list(labels_count.items())[:6]):
            ax.text(sidebar_x + 10, lb_y - 18*(j+1), f"{label}: {count}",
                    fontsize=9, color="#aaa")

    content_x = 260
    content_y = FRAME_H - 130

    if phase == "graph_viz" and graph_data:
        draw_graph_viz(ax, graph_data, content_x, content_y - 30)
    elif phase == "qna" and qa_result:
        draw_qa_section(ax, qa_result, content_x, content_y)
        if graph_data:
            draw_graph_viz_small(ax, graph_data, content_x + 400, content_y - 20)
    elif phase == "nodes":
        if graph_data:
            draw_node_list(ax, graph_data, content_x, content_y)
    else:
        draw_intro(ax, content_x, content_y)

    ax.text(FRAME_W - 30, 25, "GitHub: kunalGupta5780/GraphHacks", ha="right", fontsize=10, color="#555")
    ax.text(FRAME_W - 30, 10, "API: /api/status /api/graph_data /api/ask /docs",
            ha="right", fontsize=9, color="#444")

    fig.canvas.draw()
    img = np.asarray(fig.canvas.buffer_rgba())[:, :, :3]
    plt.close(fig)
    return img


def draw_graph_viz(ax, graph_data, x, y, width=500, height=300):
    nodes = graph_data.get("nodes", [])
    edges = graph_data.get("edges", [])
    n = len(nodes)
    if n == 0:
        return
    radius = min(width, height) / 2 - 30
    center_x, center_y = x + width/2, y + height/2 - 50
    pos = {}
    for i, node in enumerate(nodes):
        angle = 2 * np.pi * i / n
        pos[node["id"]] = (center_x + radius*np.cos(angle), center_y + radius*np.sin(angle))
        color = COLORS.get(node.get("labels", [""])[0], "#00aaff")
        circle = Circle(pos[node["id"]], 12, color=color, zorder=5)
        ax.add_patch(circle)
        circle.set_edgecolor("#fff")
        circle.set_linewidth(1.5)
        ax.text(pos[node["id"]][0]+16, pos[node["id"]][1], node.get("label","")[:8],
                fontsize=5, color="#aaa", va="center")
    for edge in edges:
        src, tgt = pos.get(edge["from"]), pos.get(edge["to"])
        if src and tgt:
            dx, dy = tgt[0]-src[0], tgt[1]-src[1]
            dist = np.sqrt(dx**2+dy**2)
            if dist > 0:
                offset = 14
                arrow = FancyArrowPatch(
                    (src[0]+dx/dist*offset, src[1]+dy/dist*offset),
                    (tgt[0]-dx/dist*offset, tgt[1]-dy/dist*offset),
                    arrowstyle="->", mutation_scale=5, color="#333", zorder=3)
                ax.add_patch(arrow)
    ax.text(x, y, f"Knowledge Graph: {n} nodes, {len(edges)} edges",
            fontsize=12, color="#00ff88")


def draw_graph_viz_small(ax, graph_data, x, y, width=300, height=200):
    nodes = graph_data.get("nodes", [])
    if not nodes:
        return
    n = min(len(nodes), 20)
    radius = min(width, height)/2 - 20
    cx, cy = x + width/2, y + height/2 - 20
    for i, node in enumerate(nodes[:n]):
        angle = 2*np.pi*i/n
        px = cx + radius*np.cos(angle)
        py = cy + radius*np.sin(angle)
        color = COLORS.get(node.get("labels", [""])[0], "#00aaff")
        ax.add_patch(Circle((px, py), 6, color=color, zorder=5))


def draw_qa_section(ax, qa_result, x, y):
    box = FancyBboxPatch((x, y), 380, 180, boxstyle="round,pad=12",
                         linewidth=1, edgecolor="#333", facecolor="#151525")
    ax.add_patch(box)
    q = qa_result.get("question", "")[:60]
    a = qa_result.get("answer", "")[:150]
    conf = qa_result.get("confidence", 0)
    ax.text(x+15, y+150, "Ask Section", fontsize=12, color="#00ff88")
    ax.text(x+15, y+130, f"Q: {q}...", fontsize=9, color="#aaa")
    conf_color = "#00ff88" if conf >= 0.7 else "#ffaa00" if conf >= 0.4 else "#ff4444"
    ax.text(x+300, y+130, f"{conf*100:.0f}%", fontsize=10, fontweight="bold",
            color=conf_color, ha="right")
    ax.text(x+15, y+100, f"A: {a}...", fontsize=8, color="#ccc")
    steps = qa_result.get("steps", [])
    for i, step in enumerate(steps[:3]):
        desc = step.get("description", "")[:50]
        ax.text(x+15, y+80-i*15, f"Step {i+1}: {desc}...", fontsize=7, color="#888")


def draw_node_list(ax, graph_data, x, y):
    nodes = graph_data.get("nodes", [])
    if not nodes:
        return
    box = FancyBboxPatch((x, y-20), 500, 220, boxstyle="round,pad=12",
                         linewidth=1, edgecolor="#333", facecolor="#151525")
    ax.add_patch(box)
    ax.text(x+15, y+180, "Node Detail Panel", fontsize=14, color="#00ff88")
    ax.text(x+15, y+160, f"Showing {len(nodes)} nodes in the graph", fontsize=10, color="#aaa")
    for i, node in enumerate(nodes[:8]):
        row_y = y + 140 - i*18
        color = COLORS.get(node.get("labels", [""])[0], "#00aaff")
        ax.add_patch(Circle((x+25, row_y), 4, color=color, zorder=5))
        ax.text(x+35, row_y, node.get("label", node["id"])[:30], fontsize=7, color="#ccc", va="center")


def draw_intro(ax, x, y):
    features = [
        "Interactive vis.js Knowledge Graph",
        "Live Graph Status (auto-refresh)",
        "Node Detail Panel (click to inspect)",
        "Real-time Q&A with Confidence Scores",
        "Search & Filter",
        "3 Tracks: Agent, Memory, Company Brain",
    ]
    ax.text(x, y+150, "Dashboard Features:", fontsize=14, color="#00ff88")
    for i, feat in enumerate(features):
        ax.text(x, y+130-i*20, f"+ {feat}", fontsize=11, color="#ccc")
    box = FancyBboxPatch((x+230, y-30), 320, 140, boxstyle="round,pad=12",
                         linewidth=1, edgecolor="#333", facecolor="#151525")
    ax.add_patch(box)
    ax.text(x+245, y+100, "API Endpoints", fontsize=12, color="#00ff88")
    endpoints = ["GET  /api/status", "GET  /api/graph_data", "POST /api/ask",
                 "GET  /api/memory/default", "POST /api/seed", "GET  /docs"]
    for i, ep in enumerate(endpoints):
        color = "#00ff88" if ep == "POST /api/ask" else "#aaa"
        ax.text(x+245, y+80-i*14, ep, fontsize=9, color=color, fontfamily="monospace")


def main():
    print("Starting server...")
    server_proc = start_server()
    print("Server is up. Fetching data...")

    try:
        graph_data = fetch_graph_data()
        status_data = fetch_status()
        qa_result = ask_question("Who has worked on the FalkorDB system?")

        print(f"Got {len(graph_data.get('nodes', []))} nodes, "
              f"{len(graph_data.get('edges', []))} edges")

        frames = []

        # Intro (3s = 72 frames)
        for i in range(72):
            frames.append(draw_dashboard_frame(
                i, title="GraphHacks Dashboard",
                subtitle="Agent with a Graph Context Layer | Built with FalkorDB",
                phase="intro"))

        # Graph visualization (3s)
        for i in range(72):
            print(f"  Rendering graph frame {i+1}/72...", end="\r")
            frames.append(draw_dashboard_frame(
                i, graph_data=graph_data, status_data=status_data,
                title="Knowledge Graph Visualization", phase="graph_viz"))

        # Node detail panel (2s)
        for i in range(48):
            frames.append(draw_dashboard_frame(
                i, graph_data=graph_data, status_data=status_data,
                title="Node Detail Panel - Click to Inspect Properties",
                phase="nodes"))

        # Q&A interaction (3s)
        for i in range(72):
            frames.append(draw_dashboard_frame(
                i, graph_data=graph_data, status_data=status_data,
                title="Interactive Q&A with Confidence Scores",
                phase="qna", qa_result=qa_result))

        print(f"\nRendering {len(frames)} frames to video...")
        imageio.mimwrite(
            VIDEO_PATH, frames,
            fps=FPS, codec="libx264", quality=8,
        )
        print(f"Video saved to: {VIDEO_PATH}")
        print(f"File size: {os.path.getsize(VIDEO_PATH) / (1024*1024):.1f} MB")

    finally:
        stop_server(server_proc)


if __name__ == "__main__":
    main()

