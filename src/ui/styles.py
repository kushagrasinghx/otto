"""shadcn-inspired Qt style sheets (dark zinc palette).

Palette reference:
  background / popover  zinc-950  #09090b
  card                  zinc-900  #18181b
  zinc-800 #27272a · zinc-700 #3f3f46 · zinc-500 #71717a · zinc-400 #a1a1aa
  foreground            #fafafa / #f4f4f5
  accents               blue-500 #3b82f6 · green-500 #22c55e · red-500 #ef4444
"""

# --- Spotlight command box (frosted / acrylic, dark zinc) ------------------
SPOTLIGHT_QSS = """
#card {
    background-color: rgba(9, 9, 11, 210);
    border: 1px solid rgba(255, 255, 255, 18);
    border-radius: 16px;
}
#card[blur="true"] {
    /* Acrylic tint (see blur.py) already supplies the dark frost, so keep
       this Qt overlay nearly transparent — otherwise it stacks on top and
       hides the blurred desktop. */
    background-color: rgba(9, 9, 11, 30);
    border: 1px solid rgba(255, 255, 255, 26);
}
#prompt {
    background: transparent;
    border: none;
    color: #ffffff;
    font-size: 22px;
    font-family: 'Segoe UI Variable Display', 'Segoe UI', sans-serif;
    selection-background-color: rgba(59, 130, 246, 150);
}
#sep {
    background-color: rgba(255, 255, 255, 16);
    border: none;
    max-height: 1px;
    min-height: 1px;
}
#hint {
    color: #a1a1aa;
    font-size: 13px;
    font-family: 'Segoe UI', sans-serif;
    background: transparent;
    border: none;
}
"""

# --- Step cards (bottom-right) ----------------------------------------------
# #stepCard uses the EXACT same surface values as the Spotlight box's #card
# above (same fill alpha, border, radius, and blur-property overlay) so the
# frosted acrylic reads identically on both.
STEP_QSS = """
#stepCard {
    background-color: rgba(9, 9, 11, 210);
    border: 1px solid rgba(255, 255, 255, 18);
    border-radius: 16px;
}
#stepCard[blur="true"] {
    background-color: rgba(9, 9, 11, 30);
    border: 1px solid rgba(255, 255, 255, 26);
}
#stepText {
    color: #e4e4e7;
    font-size: 13px;
    font-family: 'Segoe UI Variable Text', 'Segoe UI', sans-serif;
    background: transparent;
}
#iconBadge { border-radius: 7px; }
#iconBadge[kind="action"]  { background-color: rgba(59, 130, 246, 36); }
#iconBadge[kind="thought"] { background-color: rgba(212, 212, 216, 22); }
#iconBadge[kind="status"]  { background-color: rgba(161, 161, 170, 22); }
#iconBadge[kind="result"]  { background-color: rgba(34, 197, 94, 36); }
#iconBadge[kind="error"]   { background-color: rgba(239, 68, 68, 36); }
#iconBadge[kind="reply"]   { background-color: rgba(228, 228, 231, 22); }
"""
