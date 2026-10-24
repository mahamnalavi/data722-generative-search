/* Product illustrations, drawn in code (no photos, no copyright or brand issues).
 * Lookup order: product type, then subcategory, then category icon.
 * Shapes with class "f" get a light fill from CSS. 64 x 64 drawing grid.
 */
(() => {
  const s = (inner) => `<svg viewBox="0 0 64 64" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${inner}</svg>`;

  const SUB = {
    // Kitchenware
    "Baking & Pastry": s('<path class="f" d="M32 40C18 32 22 8 32 8s14 24 0 32z"/><path d="M32 40c-6-10-5-30 0-32 5 2 6 22 0 32"/><rect class="f" x="29" y="42" width="6" height="16" rx="3"/>'),
    "Cookware": s('<rect class="f" x="12" y="26" width="40" height="24" rx="4"/><path d="M8 26h48M27 26c0-6 10-6 10 0M12 32H5M52 32h7"/>'),
    "Cookware Tools": s('<path d="M46 6 31 36"/><path class="f" d="M18 36a13 13 0 0 0 26 0z"/>'),
    "Measuring": s('<rect class="f" x="10" y="34" width="44" height="20" rx="4"/><path d="M8 28h48M32 28v6"/><rect x="24" y="40" width="16" height="8" rx="1"/>'),
    "Prep Tools": s('<rect class="f" x="8" y="32" width="42" height="24" rx="4"/><circle cx="44" cy="38" r="2"/><path class="f" d="m10 26 30-11 3 6-31 9z"/><path d="m40 15 13-5 2 5-12 6"/>'),
    "Serveware": s('<ellipse class="f" cx="32" cy="38" rx="16" ry="14"/><path d="M24 25q8-7 16 0M16 36q-8-4-10-12M48 32q10 2 0 14M22 53h20"/><circle cx="32" cy="19" r="2"/>'),
    "Small Appliances": s('<path class="f" d="M14 14h30q8 0 8 8 0 6-8 6H22q-8 0-8-8z"/><path d="M22 14q0-10 10-10t10 10M26 28v14M36 28v14"/><ellipse cx="26" cy="49" rx="4" ry="6"/><ellipse cx="36" cy="49" rx="4" ry="6"/>'),
    "Storage Jars": s('<rect class="f" x="18" y="20" width="28" height="36" rx="6"/><rect x="20" y="12" width="24" height="8" rx="2"/><rect x="24" y="32" width="16" height="10" rx="1"/>'),
    // Tools
    "Electrical": s('<path class="f" d="M32 8a14 14 0 0 1 10 24q-2 4-2 8H24q0-4-2-8A14 14 0 0 1 32 8z"/><path d="M25 45h14M26 49h12M29 53h6"/>'),
    "Fixings": s('<path class="f" d="M22 10h20l-2 8H24z"/><path d="M28 18v28l4 10 4-10V18M28 25l8 4M28 33l8 4M28 41l8 3"/>'),
    "Hand Tools": s('<rect class="f" x="10" y="10" width="32" height="11" rx="2"/><path d="M42 12q10 0 12 9"/><rect x="23" y="21" width="7" height="36" rx="3"/>'),
    "Ladders": s('<path d="M20 6 14 58M44 6l6 52M19 16h26M18 26h28M17 36h30M16 46h32"/>'),
    "Measuring & Detection": s('<rect class="f" x="8" y="18" width="32" height="32" rx="8"/><circle cx="24" cy="34" r="6"/><path d="M40 42h18v6H40M46 42v3M52 42v3"/>'),
    "Painting & Finishing": s('<rect class="f" x="10" y="10" width="34" height="14" rx="4"/><path d="M44 17h8v13H32v10"/><rect x="29" y="40" width="6" height="18" rx="3"/>'),
    "Plumbing": s('<path d="M6 30h16"/><rect class="f" x="22" y="24" width="16" height="14" rx="3"/><path d="M38 30h10q6 0 6 6v6M30 24V14M24 14h12M54 48q-3 4 0 6 3-2 0-6z"/>'),
    "Power Tools": s('<path class="f" d="M12 16h32q6 0 6 6v4q0 4-6 4H34l-4 22H20l4-22H12z"/><rect x="50" y="19" width="6" height="8"/><path d="M56 23h6"/><rect x="16" y="50" width="20" height="8" rx="2"/>'),
    "Tool Storage": s('<rect class="f" x="8" y="24" width="48" height="28" rx="3"/><path d="M8 34h48M24 24v-8h16v8"/><rect x="29" y="31" width="6" height="6"/>'),
    // Organizers
    "Bathroom Storage": s('<path d="M14 8v48M50 8v48M14 26h36M14 46h36"/><rect class="f" x="18" y="12" width="8" height="14" rx="2"/><rect x="30" y="15" width="6" height="11" rx="2"/><rect class="f" x="20" y="33" width="10" height="13" rx="2"/><circle cx="40" cy="40" r="5"/>'),
    "Bedroom Storage": s('<rect class="f" x="10" y="26" width="44" height="28" rx="3"/><rect x="8" y="18" width="48" height="8" rx="2"/><rect x="26" y="36" width="12" height="4" rx="2"/>'),
    "Desk & Office": s('<rect class="f" x="10" y="28" width="18" height="26" rx="2"/><path d="m15 28-2-18M20 28V8M24 28l4-16M36 36v-6h16v6"/><rect x="34" y="36" width="20" height="18" rx="2"/>'),
    "Drawer Storage": s('<rect x="8" y="16" width="48" height="32" rx="3"/><path d="M24 16v32M40 16v32M40 32h16"/><rect class="f" x="10" y="18" width="12" height="28"/><path d="M8 54h48"/>'),
    "Entryway": s('<rect class="f" x="10" y="12" width="44" height="12" rx="3"/><path d="M20 24v8M36 24v6M20 40v14M36 38v12M20 50h4M36 46h4"/><circle cx="20" cy="36" r="4"/><circle cx="36" cy="34" r="4"/>'),
    "Kitchen Storage": s('<path d="M8 42h48M12 42v6M52 42v6"/><rect class="f" x="12" y="26" width="10" height="16" rx="2"/><rect x="26" y="20" width="12" height="22" rx="2"/><rect class="f" x="42" y="28" width="10" height="14" rx="2"/><path d="M26 26h12"/>'),
    "Laundry": s('<path class="f" d="M12 26h40l-4 30H16z"/><path d="M10 26h44M18 34h28M19 42h26M20 50h24M24 26q4-10 12-6 4 2 6 6"/>'),
    "Wardrobe Storage": s('<path d="M32 22v-6q0-6 5-6t5 5"/><path class="f" d="M32 22 8 40q-3 4 2 4h44q5 0 2-4z"/>'),
    // Furniture
    "Bedroom": s('<rect x="6" y="16" width="8" height="38" rx="2"/><rect class="f" x="14" y="32" width="44" height="12" rx="2"/><rect x="16" y="25" width="13" height="7" rx="3"/><path d="M56 44v10M14 44v10"/>'),
    "Desks": s('<path d="M6 26h52M10 26v30M54 26v30M18 24l4-11h13l2 11"/><rect class="f" x="38" y="26" width="16" height="12"/><path d="M44 32h4"/>'),
    "Kitchen Furniture": s('<rect class="f" x="20" y="14" width="24" height="7" rx="2"/><path d="M22 21 16 56M42 21l6 35M19 38h26"/>'),
    "Living Room": s('<rect class="f" x="12" y="18" width="40" height="16" rx="4"/><rect x="12" y="34" width="40" height="10" rx="2"/><rect class="f" x="5" y="26" width="8" height="20" rx="3"/><rect class="f" x="51" y="26" width="8" height="20" rx="3"/><path d="M10 46v6M54 46v6"/>'),
    "Seating": s('<rect class="f" x="20" y="8" width="24" height="24" rx="3"/><rect x="16" y="32" width="32" height="8" rx="2"/><path d="M20 40v18M44 40v18"/>'),
    "Storage Furniture": s('<rect x="14" y="6" width="36" height="52" rx="2"/><path d="M14 22h36M14 38h36"/><rect class="f" x="18" y="10" width="4" height="12"/><rect class="f" x="23" y="12" width="4" height="10"/><rect class="f" x="30" y="27" width="10" height="11"/><path d="M14 58v2M50 58v2"/>'),
    "Tables": s('<rect class="f" x="8" y="24" width="48" height="6" rx="2"/><path d="M14 30v26M50 30v26M28 24v-6h8v6"/><path d="M30 18q2-8 4 0"/>'),
  };
  // Organizers and Furniture both have an "Entryway"; furniture version keyed separately.
  SUB["Furniture:Entryway"] = s('<rect class="f" x="8" y="24" width="48" height="7" rx="2"/><path d="M12 31v24M52 31v24M12 44h40"/><path d="M18 44q0-4 6-4h2v4M36 44q0-4 6-4h2v4"/>');

  const TYPE = {
    egg_separator: s('<path d="M10 28h44M54 28h8"/><path class="f" d="M14 28q18 26 36 0z"/><circle cx="32" cy="34" r="6" fill="currentColor" fill-opacity=".35"/><path d="M22 36l2 4M42 36l-2 4M24 50v4M32 52v5M40 50v4"/>'),
    mandoline_slicer: s('<path class="f" d="M8 48 52 20l6 8-44 28z"/><path d="M27 37l9-6M14 56l-2 5M58 28l2 8"/><ellipse cx="44" cy="52" rx="6" ry="2"/><ellipse cx="54" cy="56" rx="5" ry="2"/>'),
    pressure_cooker: s('<rect class="f" x="12" y="28" width="40" height="24" rx="4"/><path d="M10 28q22-12 44 0M44 21h18"/><rect x="29" y="11" width="6" height="8" rx="1"/>'),
    tawa: s('<ellipse class="f" cx="28" cy="38" rx="22" ry="8"/><path d="M50 37h12"/><ellipse cx="28" cy="36" rx="12" ry="4"/>'),
    emergency_light: s('<rect class="f" x="8" y="20" width="48" height="26" rx="4"/><path d="M20 20v-8h24v8M8 52l-4 4M56 52l4 4M32 50v8"/><circle cx="18" cy="29" r="2"/><circle cx="26" cy="29" r="2"/><circle cx="34" cy="29" r="2"/><circle cx="42" cy="29" r="2"/><circle cx="18" cy="37" r="2"/><circle cx="26" cy="37" r="2"/><circle cx="34" cy="37" r="2"/><circle cx="42" cy="37" r="2"/>'),
    stud_finder: s('<rect class="f" x="20" y="8" width="24" height="48" rx="8"/><rect x="25" y="14" width="14" height="10" rx="1"/><circle cx="32" cy="36" r="4"/><path d="M10 26q-4 6 0 12M54 26q4 6 0 12M5 22q-6 10 0 20M59 22q6 10 0 20"/>'),
    boil_over_disc: s('<path d="M12 28v24q0 4 4 4h32q4 0 4-4V28M8 28h48"/><ellipse class="f" cx="32" cy="40" rx="9" ry="3"/><circle cx="20" cy="46" r="1.5"/><circle cx="44" cy="47" r="1.5"/><path d="M24 20q-3-4 0-8M32 20q-3-4 0-8M40 20q-3-4 0-8"/>'),
    prayer_chair: s('<rect class="f" x="16" y="8" width="10" height="28" rx="3"/><rect class="f" x="20" y="36" width="28" height="6" rx="2"/><path d="M21 42l-6 16M46 42l6 16M21 36V8M32 42l8 16"/>'),
    manual_chopper: s('<path class="f" d="M12 30h40l-4 26H16z"/><rect x="10" y="24" width="44" height="6" rx="3"/><path d="M54 27h6M22 44l6-6 6 6 6-6"/><circle cx="61" cy="27" r="2"/>'),
    masala_dabba: s('<ellipse class="f" cx="32" cy="34" rx="26" ry="16"/><circle cx="32" cy="34" r="5"/><circle cx="18" cy="30" r="5"/><circle cx="46" cy="30" r="5"/><circle cx="22" cy="42" r="5"/><circle cx="42" cy="42" r="5"/><circle cx="26" cy="23" r="4"/><circle cx="38" cy="23" r="4"/>'),
    lazy_susan: s('<ellipse class="f" cx="32" cy="44" rx="26" ry="8"/><path d="M26 52v4h12v-4"/><rect x="18" y="28" width="7" height="14" rx="2"/><rect class="f" x="29" y="24" width="7" height="18" rx="2"/><rect x="40" y="30" width="7" height="12" rx="2"/><path d="M50 22q6 4 4 10"/>'),
    spice_rack: s('<path d="M10 22h44M10 38h44M10 54h44M10 14v42M54 14v42"/><rect class="f" x="15" y="12" width="7" height="10" rx="1"/><rect x="27" y="12" width="7" height="10" rx="1"/><rect class="f" x="39" y="12" width="7" height="10" rx="1"/><rect x="15" y="28" width="7" height="10" rx="1"/><rect class="f" x="27" y="28" width="7" height="10" rx="1"/><rect class="f" x="21" y="44" width="7" height="10" rx="1"/><rect x="34" y="44" width="7" height="10" rx="1"/>'),
    madhani: s('<path d="M32 4v38M24 10h16"/><path class="f" d="m32 42 4 6 7 1-5 5 1 7-7-3-7 3 1-7-5-5 7-1z"/>'),
    charpai: s('<rect class="f" x="6" y="24" width="52" height="14" rx="2"/><path d="M12 24l8 14M22 24l8 14M32 24l8 14M42 24l8 14M10 38v16M54 38v16M10 24v-4M54 24v-4"/>'),
    mooda: s('<path class="f" d="M18 18h28l-8 18 8 18H18l8-18z"/><path d="M22 26h20M24 46h16M18 18v-2h28v2"/>'),
    rehal: s('<path d="M14 54 50 22M14 22l36 32"/><path class="f" d="M16 22q16-10 32 0l-16 14z"/>'),
    kitchen_tongs: s('<path d="M10 54 40 8M18 58 52 12M40 8q6-4 12 4"/><path class="f" d="M8 50l6 6 6-4-6-6z"/>'),
    knife_sharpener: s('<rect class="f" x="8" y="38" width="48" height="12" rx="4"/><path d="M22 38v-6h20v6M26 32l4-6h4l4 6"/><path d="M14 22 50 14l2 4-36 8z"/>'),
    drain_auger: s('<circle class="f" cx="20" cy="24" r="12"/><circle cx="20" cy="24" r="4"/><path d="M32 24q12 0 14 10t8 12 4 8"/><path d="M8 24H2"/>'),
    salad_spinner: s('<path class="f" d="M10 26h44l-4 28H14z"/><rect x="8" y="20" width="48" height="6" rx="3"/><path d="M32 20v-8M28 12h8M20 36q12 8 24 0"/>'),
    garlic_press: s('<path class="f" d="M8 30h22l6 6v4H14q-6 0-6-6z"/><path d="M36 36l22-8M36 40l22 6M26 30l6-10h24"/>'),
    vacuum_bags: s('<path class="f" d="M10 18h36l6 6v28H10z"/><path d="M10 26h42M46 18v6h6M30 38q4-4 8 0"/><path d="M56 44h6v10h-6"/>'),
  };

  window.illustrationFor = (p) =>
    TYPE[p.product_type] || SUB[`${p.category}:${p.subcategory}`] || SUB[p.subcategory] || null;
})();
