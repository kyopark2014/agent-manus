// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0

/**
 * @file layoutGuidance.js
 * @description Comprehensive layout guidance for AI agents
 */

/**
 * Get complete layout guidance documentation
 * @returns {Object} Structured guidance content
 */
export function getLayoutGuidance() {
  return {
    summary:
      "Comprehensive guidance for creating well-structured, presentation-ready diagrams using grid-based planning, layout patterns, and optimization tools.",

    principles: [
      "Plan Before Placing: Use grid-based planning approach",
      "Grid Alignment: Position on consistent grid (50px or 100px spacing)",
      "Hierarchical Organization: Show relationships and importance visually",
      "Balanced Composition: Distribute elements evenly to avoid clustering",
      "Clean Connections: Route connectors to minimize crossings and overlaps",
    ],

    gridSystem: {
      description:
        "Grid-based planning system for visualizing layouts before implementation",
      gridSizes: {
        "8x8": "Simple diagrams (3-8 elements)",
        "10x10": "Medium diagrams (8-15 elements)",
        "12x12": "Complex diagrams (15+ elements)",
      },
      coordinateFormula:
        "x = column * spacing + margin, y = row * spacing + margin",
      recommendedSpacing: {
        compact: 50,
        standard: 100,
        spacious: 150,
      },
      recommendedMargin: 50,
    },

    patterns: {
      "single-center": {
        name: "Single Center (Star/Hub)",
        useCase: "One central element with satellites",
        example: "Microservices around API gateway",
        description:
          "Place center at grid center, distribute satellites in circular pattern",
      },
      "dual-center": {
        name: "Dual Centers (Balanced)",
        useCase: "Two main systems or environments",
        example: "On-premise vs cloud, frontend vs backend",
        description: "Place two centers, group satellites around each",
      },
      triangle: {
        name: "Triangle (Three Centers)",
        useCase: "Three-tier architecture or triangular relationships",
        example: "Three environments, three-tier app",
        description:
          "Place centers in triangle formation, distribute satellites",
      },
      linear: {
        name: "Linear Flow (Left-to-Right)",
        useCase: "Sequential processes, pipelines",
        example: "Data flows, CI/CD pipelines",
        description: "Use horizontal layout with consistent spacing",
      },
      tree: {
        name: "Hierarchical Tree",
        useCase: "Parent-child relationships",
        example: "Org charts, component hierarchies",
        description: "Root at top, children distributed below",
      },
      grid: {
        name: "Grid Layout",
        useCase: "Many elements without clear hierarchy",
        example: "Dashboards, icon galleries",
        description: "Arrange in rows and columns",
      },
    },

    tools: {
      auto_layout: {
        description: "Automatically arrange cells using predefined algorithms",
        parameters: [
          "layout_type",
          "spacing",
          "start_x",
          "start_y",
          "cell_ids",
        ],
        whenToUse: [
          "Initial placement",
          "Reorganizing layouts",
          "Creating uniform spacing",
        ],
      },
      align_cells: {
        description: "Align multiple cells along a common axis",
        parameters: ["cell_ids", "alignment"],
        whenToUse: [
          "Clean up alignment",
          "Create columns/rows",
          "Align labels with icons",
        ],
      },
      distribute_cells: {
        description: "Distribute cells evenly along an axis",
        parameters: ["cell_ids", "direction", "spacing"],
        whenToUse: [
          "Even spacing",
          "Balance visual weight",
          "After adding elements",
        ],
      },
      snap_to_grid: {
        description: "Snap positions to grid for pixel-perfect alignment",
        parameters: ["grid_size", "cell_ids"],
        whenToUse: ["Final cleanup", "Consistent positioning", "Before export"],
      },
    },

    workflow: {
      planning: [
        "Identify element count and types",
        "Choose layout pattern",
        "Create planning grid",
        "Calculate coordinates",
      ],
      implementation: [
        "Create elements in logical order",
        "Apply initial layout",
        "Refine alignment",
        "Add connectors",
        "Final cleanup",
      ],
      validation: [
        "Run validate_diagram",
        "Check for overlaps",
        "Adjust as needed",
      ],
    },

    connectorRouting: {
      orthogonal:
        "Best for technical diagrams, flowcharts (edgeStyle=orthogonalEdgeStyle)",
      straight:
        "Best for simple relationships, network diagrams (edgeStyle=none)",
      curved: "Best for organic flows, user journeys (edgeStyle=curved)",
    },

    decisionTree: `
How many main elements/groups?
├─ 1 main element → Single Center Pattern
├─ 2 main elements → Dual Centers Pattern
├─ 3 main elements → Triangle Pattern
├─ Sequential flow (4-10) → Linear Flow Pattern
├─ Hierarchical → Tree Pattern
└─ Many elements (10+) → Grid Pattern`,
  };
}

/**
 * Get guidance as formatted text for prompt injection
 * @returns {string} Formatted guidance text
 */
export function getLayoutGuidanceText() {
  const guidance = getLayoutGuidance();

  let text = "# Diagram Layout Guidance\n\n";
  text += "## Key Principles\n";
  guidance.principles.forEach((p) => (text += `- ${p}\n`));

  text += "\n## Grid System\n";
  text += `${guidance.gridSystem.description}\n\n`;
  text += "Grid Sizes:\n";
  Object.entries(guidance.gridSystem.gridSizes).forEach(([size, desc]) => {
    text += `- ${size}: ${desc}\n`;
  });

  text += `\nCoordinate Formula: ${guidance.gridSystem.coordinateFormula}\n`;
  text += `Recommended Spacing: ${JSON.stringify(guidance.gridSystem.recommendedSpacing)}\n`;
  text += `Recommended Margin: ${guidance.gridSystem.recommendedMargin}px\n`;

  text += "\n## Layout Patterns\n";
  Object.entries(guidance.patterns).forEach(([_key, pattern]) => {
    text += `\n### ${pattern.name}\n`;
    text += `Use Case: ${pattern.useCase}\n`;
    text += `Example: ${pattern.example}\n`;
    text += `Description: ${pattern.description}\n`;
  });

  text += "\n## Available Tools\n";
  Object.entries(guidance.tools).forEach(([name, tool]) => {
    text += `\n### ${name}\n`;
    text += `${tool.description}\n`;
    text += `When to use: ${tool.whenToUse.join(", ")}\n`;
  });

  text += "\n## Workflow\n";
  text += "\nPlanning Phase:\n";
  guidance.workflow.planning.forEach(
    (step, i) => (text += `${i + 1}. ${step}\n`),
  );
  text += "\nImplementation Phase:\n";
  guidance.workflow.implementation.forEach(
    (step, i) => (text += `${i + 1}. ${step}\n`),
  );
  text += "\nValidation Phase:\n";
  guidance.workflow.validation.forEach(
    (step, i) => (text += `${i + 1}. ${step}\n`),
  );

  text += `\n## Decision Tree\n${guidance.decisionTree}\n`;

  return text;
}
