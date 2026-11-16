// FLASH sample-holder geometry, shared by the Motion and Run pages.
// Units are motor steps unless a name says mm. Motor 0 = X (right +), motor 1 = Y (up +).
// Row 0 is the TOP row (A), so it has the largest Y.
(function (global) {
    const stepPerInch = 15837.6;
    const mmPerInch = 25.4;
    const sectionSpacing = 5.5 * stepPerInch;

    const holderTypes = {
        '3x2': { name: '3x2 Well Plate', plate: true, cols: 3, rows: 2, xSpacing: 1.5 * stepPerInch, ySpacing: 1.5 * stepPerInch, xOffset: 0, yOffset: 0.25 * stepPerInch },
        '4x3': { name: '4x3 Well Plate', plate: true, cols: 4, rows: 3, xSpacing: 1.0 * stepPerInch, ySpacing: 1.0 * stepPerInch, xOffset: 0, yOffset: 0 },
        '6x4': { name: '6x4 Well Plate', plate: true, cols: 6, rows: 4, xSpacing: 19.2 * stepPerInch / mmPerInch, ySpacing: 19.2 * stepPerInch / mmPerInch, xOffset: -9.9 * stepPerInch / mmPerInch, yOffset: -3.4 * stepPerInch / mmPerInch },
        '12x8': { name: '12x8 Well Plate', plate: true, cols: 12, rows: 8, xSpacing: 9 * stepPerInch / mmPerInch, ySpacing: 9 * stepPerInch / mmPerInch, xOffset: -11.4 * stepPerInch / mmPerInch, yOffset: -6.1 * stepPerInch / mmPerInch },
        'tubes': { name: 'Test Tube Rack', plate: false, cols: 3, rows: 1, xSpacing: 1.5 * stepPerInch, ySpacing: 1.5 * stepPerInch, xOffset: 0, yOffset: -5 * stepPerInch / mmPerInch },
        'puptubes': { name: 'Pup Tube Rack', plate: false, cols: 3, rows: 1, xSpacing: 1.5 * stepPerInch, ySpacing: 1.5 * stepPerInch, xOffset: -7 * stepPerInch / mmPerInch, yOffset: 31 * stepPerInch / mmPerInch },
        'l4l5tubes': { name: 'L4/L5 Tube Rack', plate: false, cols: 3, rows: 1, xSpacing: 1.5 * stepPerInch, ySpacing: 1.5 * stepPerInch, xOffset: 0, yOffset: 30 * stepPerInch / mmPerInch },
        'microtubes': { name: 'Micro Tube Rack', plate: false, cols: 4, rows: 2, xSpacing: 1.0 * stepPerInch, ySpacing: 1.75 * stepPerInch, xOffset: 0, yOffset: -0.4 * stepPerInch },
    };

    const originOffsets = { 1: { x: 0, y: 0 }, 2: { x: sectionSpacing, y: 0 } };

    function mmToSteps(mm) { return mm * stepPerInch / mmPerInch; }
    function stepsToMm(steps) { return steps * mmPerInch / stepPerInch; }

    // Linear interpolation in the Y-trim table (x and y in steps), flat beyond the ends.
    function yCorrection(corrections, x) {
        const c = (corrections || []).slice().sort((a, b) => a.x - b.x);
        if (c.length === 0) return 0;
        if (x <= c[0].x) return c[0].y;
        for (let i = 0; i < c.length - 1; i++) {
            if (x >= c[i].x && x <= c[i + 1].x) {
                const slope = (c[i + 1].y - c[i].y) / (c[i + 1].x - c[i].x || 1);
                return c[i].y + slope * (x - c[i].x);
            }
        }
        return c[c.length - 1].y;
    }

    // Same arithmetic as the original targeting page.
    function targetPosition(loadout, section, col, row, type) {
        type = type || loadout.sections[String(section)];
        const config = holderTypes[type];
        const off = loadout.targetOffsetMm || { x: 0, y: 0 };
        const x = originOffsets[section].x + config.xOffset + col * config.xSpacing + mmToSteps(off.x);
        const baseY = originOffsets[section].y + config.yOffset + (config.rows - 1 - row) * config.ySpacing;
        const y = baseY + yCorrection(loadout.yCorrections, x) + mmToSteps(off.y);
        return { x: Math.round(x), y: Math.round(y) };
    }

    function wellName(row, col) { return `${String.fromCharCode(65 + row)}${col + 1}`; }

    // Every target in the current loadout: {id, label, section, row, col, x, y, plate}
    function allTargets(loadout) {
        const out = [];
        for (const section of [1, 2]) {
            const type = loadout.sections[String(section)];
            const cfg = holderTypes[type];
            if (!cfg) continue;
            for (let row = 0; row < cfg.rows; row++) {
                for (let col = 0; col < cfg.cols; col++) {
                    const p = targetPosition(loadout, section, col, row, type);
                    const w = wellName(row, col);
                    out.push({ id: `${section}:${w}`, label: `S${section}-${w}`, well: w, section, row, col, type, plate: cfg.plate, x: p.x, y: p.y });
                }
            }
        }
        return out;
    }

    global.FlashGeometry = { stepPerInch, mmPerInch, sectionSpacing, holderTypes, originOffsets, mmToSteps, stepsToMm, yCorrection, targetPosition, wellName, allTargets };
})(window);
