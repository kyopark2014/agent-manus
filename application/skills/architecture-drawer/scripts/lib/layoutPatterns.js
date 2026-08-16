// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0

/**
 * @file layoutPatterns.js
 * @description Layout pattern generators for different diagram types
 */

/**
 * Calculate pixel coordinates from grid position
 */
export function gridToPixels(col, row, spacing, margin) {
  return {
    x: col * spacing + margin,
    y: row * spacing + margin,
  };
}

/**
 * Generate single-center (star/hub) layout
 */
export function generateSingleCenterLayout(elements, options = {}) {
  const { gridSize = 8, spacing = 100, margin = 50 } = options;

  if (elements.length === 0) {
    throw new Error("At least one element required");
  }

  const center = gridToPixels(
    Math.floor(gridSize / 2),
    Math.floor(gridSize / 2),
    spacing,
    margin,
  );
  const coordinates = [];
  const connections = [];

  coordinates.push({
    id: elements[0].id,
    x: center.x,
    y: center.y,
    role: "center",
  });

  const satellites = elements.slice(1);
  const angleStep = (2 * Math.PI) / Math.max(satellites.length, 1);
  const radius = spacing * 2;

  satellites.forEach((elem, i) => {
    const angle = i * angleStep;
    const x = center.x + Math.cos(angle) * radius;
    const y = center.y + Math.sin(angle) * radius;

    coordinates.push({
      id: elem.id,
      x: Math.round(x),
      y: Math.round(y),
      role: "satellite",
    });
    connections.push({ from: elements[0].id, to: elem.id });
  });

  return {
    pattern: "single-center",
    gridSize,
    spacing,
    margin,
    coordinates,
    connections,
  };
}

/**
 * Generate dual-center (balanced) layout
 */
export function generateDualCenterLayout(elements, options = {}) {
  const { gridSize = 10, spacing = 100, margin = 50 } = options;

  if (elements.length < 2) {
    throw new Error("At least two elements required");
  }

  const leftCenter = gridToPixels(3, Math.floor(gridSize / 2), spacing, margin);
  const rightCenter = gridToPixels(
    gridSize - 4,
    Math.floor(gridSize / 2),
    spacing,
    margin,
  );

  const coordinates = [
    {
      id: elements[0].id,
      x: leftCenter.x,
      y: leftCenter.y,
      role: "left-center",
    },
    {
      id: elements[1].id,
      x: rightCenter.x,
      y: rightCenter.y,
      role: "right-center",
    },
  ];

  const connections = [{ from: elements[0].id, to: elements[1].id }];

  const remaining = elements.slice(2);
  const leftGroup = remaining.filter((_, i) => i % 2 === 0);
  const rightGroup = remaining.filter((_, i) => i % 2 === 1);

  leftGroup.forEach((elem, i) => {
    const offset = (i - leftGroup.length / 2) * spacing;
    coordinates.push({
      id: elem.id,
      x: leftCenter.x - spacing,
      y: leftCenter.y + offset,
      role: "left-satellite",
    });
    connections.push({ from: elements[0].id, to: elem.id });
  });

  rightGroup.forEach((elem, i) => {
    const offset = (i - rightGroup.length / 2) * spacing;
    coordinates.push({
      id: elem.id,
      x: rightCenter.x + spacing,
      y: rightCenter.y + offset,
      role: "right-satellite",
    });
    connections.push({ from: elements[1].id, to: elem.id });
  });

  return {
    pattern: "dual-center",
    gridSize,
    spacing,
    margin,
    coordinates,
    connections,
  };
}

/**
 * Generate triangle (three-center) layout
 */
export function generateTriangleLayout(elements, options = {}) {
  const { gridSize = 12, spacing = 100, margin = 50 } = options;

  if (elements.length < 3) {
    throw new Error("At least three elements required");
  }

  const topCenter = gridToPixels(Math.floor(gridSize / 2), 2, spacing, margin);
  const leftCenter = gridToPixels(2, gridSize - 3, spacing, margin);
  const rightCenter = gridToPixels(gridSize - 3, gridSize - 3, spacing, margin);

  const coordinates = [
    { id: elements[0].id, x: topCenter.x, y: topCenter.y, role: "top-center" },
    {
      id: elements[1].id,
      x: leftCenter.x,
      y: leftCenter.y,
      role: "left-center",
    },
    {
      id: elements[2].id,
      x: rightCenter.x,
      y: rightCenter.y,
      role: "right-center",
    },
  ];

  const connections = [
    { from: elements[0].id, to: elements[1].id },
    { from: elements[1].id, to: elements[2].id },
    { from: elements[2].id, to: elements[0].id },
  ];

  const remaining = elements.slice(3);
  remaining.forEach((elem, i) => {
    const centerIdx = i % 3;
    const center = coordinates[centerIdx];
    const offset = Math.floor(i / 3) * spacing;

    coordinates.push({
      id: elem.id,
      x: center.x + (centerIdx === 0 ? 0 : centerIdx === 1 ? -offset : offset),
      y: center.y + offset,
      role: `satellite-${centerIdx}`,
    });

    connections.push({ from: elements[centerIdx].id, to: elem.id });
  });

  return {
    pattern: "triangle",
    gridSize,
    spacing,
    margin,
    coordinates,
    connections,
  };
}

/**
 * Generate linear flow layout
 */
export function generateLinearLayout(elements, options = {}) {
  const {
    gridSize = 10,
    spacing = 150,
    margin = 50,
    direction = "horizontal",
  } = options;

  const coordinates = [];
  const connections = [];

  elements.forEach((elem, i) => {
    if (direction === "horizontal") {
      coordinates.push({
        id: elem.id,
        x: margin + i * spacing,
        y: margin + Math.floor(gridSize / 2) * spacing,
        role: `step-${i + 1}`,
      });
    } else {
      coordinates.push({
        id: elem.id,
        x: margin + Math.floor(gridSize / 2) * spacing,
        y: margin + i * spacing,
        role: `step-${i + 1}`,
      });
    }

    if (i > 0) {
      connections.push({ from: elements[i - 1].id, to: elem.id });
    }
  });

  return {
    pattern: "linear",
    direction,
    gridSize,
    spacing,
    margin,
    coordinates,
    connections,
  };
}

/**
 * Generate tree layout
 */
export function generateTreeLayout(elements, options = {}) {
  const { gridSize = 12, spacing = 120, margin = 50 } = options;

  if (elements.length === 0) {
    throw new Error("At least one element required");
  }

  const coordinates = [];
  const connections = [];

  const rootX = margin + Math.floor(gridSize / 2) * spacing;
  coordinates.push({
    id: elements[0].id,
    x: rootX,
    y: margin,
    role: "root",
    level: 0,
  });

  const remaining = elements.slice(1);
  const childrenPerLevel = Math.ceil(Math.sqrt(remaining.length));

  remaining.forEach((elem, i) => {
    const level = Math.floor(i / childrenPerLevel) + 1;
    const posInLevel = i % childrenPerLevel;
    const totalInLevel = Math.min(
      childrenPerLevel,
      remaining.length - (level - 1) * childrenPerLevel,
    );

    const levelWidth = (totalInLevel - 1) * spacing;
    const startX = rootX - levelWidth / 2;

    coordinates.push({
      id: elem.id,
      x: startX + posInLevel * spacing,
      y: margin + level * spacing,
      role: "child",
      level,
    });

    const parentIdx =
      level === 1
        ? 0
        : Math.floor((i - childrenPerLevel) / childrenPerLevel) + 1;
    connections.push({ from: elements[parentIdx].id, to: elem.id });
  });

  return {
    pattern: "tree",
    gridSize,
    spacing,
    margin,
    coordinates,
    connections,
  };
}

/**
 * Generate grid layout
 */
export function generateGridLayout(elements, options = {}) {
  const { gridSize = 12, spacing = 120, margin = 50, columns = 4 } = options;

  const coordinates = [];

  elements.forEach((elem, i) => {
    const col = i % columns;
    const row = Math.floor(i / columns);

    coordinates.push({
      id: elem.id,
      x: margin + col * spacing,
      y: margin + row * spacing,
      role: `cell-${i + 1}`,
    });
  });

  return {
    pattern: "grid",
    gridSize,
    spacing,
    margin,
    columns,
    coordinates,
    connections: [],
  };
}

/**
 * Select appropriate pattern based on element count and relationships
 */
export function selectPattern(
  elementCount,
  hasHierarchy = false,
  mainGroups = 1,
) {
  if (hasHierarchy) return "tree";
  if (mainGroups === 2) return "dual-center";
  if (mainGroups === 3) return "triangle";
  if (elementCount > 15) return "grid";
  if (elementCount <= 10 && mainGroups === 1) return "linear";
  return "single-center";
}
