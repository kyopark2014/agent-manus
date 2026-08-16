export { setupGlobalMocks } from './mocks/globalMocks.js';

/**
 * @file types.ts - TypeScript type definitions for DrawioAPI
 * @description Central type definitions for the draw.io API
 */
/**
 * Represents a 2D point.
 */
interface Point {
    x: number;
    y: number;
}
/**
 * Represents cell geometry (position and size).
 */
interface CellGeometry {
    x: number;
    y: number;
    width: number;
    height: number;
}
/**
 * Partial geometry for updates.
 */
interface PartialGeometry {
    x?: number;
    y?: number;
    width?: number;
    height?: number;
}
/**
 * Style properties that can be applied to cells.
 */
interface CellStyle {
    fillColor?: string;
    strokeColor?: string;
    strokeWidth?: number | string;
    fontColor?: string;
    fontSize?: number | string;
    fontFamily?: string;
    opacity?: number | string;
    rounded?: string | number;
    shadow?: string | number;
    shape?: string;
    perimeter?: string;
    verticalAlign?: string;
    align?: string;
    spacingTop?: number | string;
    spacingBottom?: number | string;
    spacingLeft?: number | string;
    spacingRight?: number | string;
    dashed?: string | number;
    dashPattern?: string;
    gradientColor?: string;
    gradientDirection?: string;
    glass?: string | number;
    labelBackgroundColor?: string;
    labelBorderColor?: string;
    [key: string]: string | number | undefined;
}
/**
 * Standard API result type with success/error pattern.
 */
interface APIResult<T = unknown> {
    success: boolean;
    data?: T;
    error?: string;
}
/**
 * Data representation of a cell.
 */
interface CellData {
    id: string;
    label: string;
    style: string;
    isVertex: boolean;
    isEdge: boolean;
    parentId: string | null;
    geometry?: CellGeometry;
    sourceId?: string | null;
    targetId?: string | null;
}
/**
 * Options for inserting a vertex.
 */
interface VertexOptions {
    id?: string | null;
    label?: string;
    geometry: CellGeometry;
    style?: string | CellStyle;
    parentId?: string;
}
/**
 * Options for inserting an edge.
 */
interface EdgeOptions {
    id?: string | null;
    label?: string;
    sourceId: string;
    targetId: string;
    style?: string | CellStyle;
    waypoints?: Point[];
}
/**
 * Options for updating a cell.
 */
interface UpdateCellOptions {
    label?: string;
    geometry?: PartialGeometry;
    style?: string | CellStyle;
}
/**
 * Information about a diagram.
 */
interface DiagramInfo {
    cellCount: number;
    vertexCount: number;
    edgeCount: number;
    pageCount: number;
    currentPageId: string | null;
}
/**
 * Page data.
 */
interface PageData {
    id: string;
    name: string;
    index: number;
}
/**
 * Icon definition from a shape library.
 */
interface IconDefinition {
    name: string;
    icon: string;
    fillColor?: string;
    width?: number;
    height?: number;
    category?: string;
}
/**
 * Group definition from a shape library.
 */
interface GroupDefinition {
    name: string;
    simple?: boolean;
    strokeColor?: string;
    fillColor?: string;
    fontColor?: string;
    icon?: string;
}
/**
 * Library information.
 */
interface LibraryInfo {
    id: string;
    name: string;
    categories: string[];
    groupTypes?: string[];
}
/**
 * Options for inserting an AWS icon.
 */
interface AwsIconOptions {
    icon?: string;
    style?: string;
    label?: string;
    geometry: PartialGeometry & {
        x: number;
        y: number;
    };
    category?: string;
    fillColor?: string;
    id?: string;
    parentId?: string;
}
/**
 * Options for inserting an AWS group.
 */
interface AwsGroupOptions {
    groupType?: string;
    style?: string;
    label?: string;
    geometry: CellGeometry;
    strokeColor?: string;
    fillColor?: string;
    fontColor?: string;
    id?: string;
    parentId?: string;
}
/**
 * AWS group type info.
 */
interface AwsGroupTypeInfo {
    type: string;
    name: string;
    hasIcon: boolean;
}
/**
 * Mock cell interface (represents mxCell).
 */
interface MockCell {
    id: string;
    value: string | null;
    geometry: MockGeometry | null;
    style: string;
    vertex: boolean;
    edge: boolean;
    parent: MockCell | null;
    children: MockCell[];
    source: MockCell | null;
    target: MockCell | null;
    getId(): string;
    getValue(): string | null;
    setValue(v: string | null): void;
    getGeometry(): MockGeometry | null;
    setGeometry(g: MockGeometry | null): void;
    getStyle(): string;
    setStyle(s: string): void;
    getParent(): MockCell | null;
    getChildCount(): number;
    getChildAt(i: number): MockCell | null;
}
/**
 * Mock geometry interface.
 */
interface MockGeometry {
    x: number;
    y: number;
    width: number;
    height: number;
    points?: Point[];
    clone(): MockGeometry;
}
/**
 * Options for creating a diagram.
 */
interface CreateDiagramOptions {
    name?: string;
}
/**
 * Options for serializing a diagram to XML.
 */
interface SerializeOptions {
    diagramName?: string;
    wrapInMxFile?: boolean;
}
/**
 * Parse result from XmlParser.
 */
interface ParseResult {
    diagramName?: string;
    pageCount?: number;
}
/**
 * SVG export options.
 */
interface SvgExportOptions {
    border?: number;
    background?: string | null;
}
/**
 * PNG export options.
 */
interface PngExportOptions {
    scale?: number;
    background?: string | null;
}
/**
 * XML validation result.
 */
interface XmlValidationResult {
    valid: boolean;
    error?: string;
    rootElement?: string;
}
/**
 * Options for building icon styles.
 */
interface IconStyleOptions {
    fillColor?: string;
    category?: string;
    type?: "resource" | "product";
}
/**
 * Options for building group styles.
 */
interface GroupStyleOptions$1 {
    strokeColor?: string;
    fillColor?: string;
    fontColor?: string;
}
/**
 * Dependencies for DrawioAPI constructor.
 */
interface DrawioAPIDependencies {
    graph?: unknown;
    model?: unknown;
    editorUi?: unknown;
}
/**
 * Types namespace for backwards compatibility.
 */
declare const Types: {};

/**
 * @file DiagramManager.ts - Document/page lifecycle operations
 * @description Manages diagram creation, loading, saving, and page operations
 */

/**
 * Manages diagram-level operations including document lifecycle and pages.
 */
declare class DiagramManager {
    private _api;
    constructor(api: DrawioAPI);
    create(): APIResult;
    clear(): APIResult;
    getXml(): APIResult<string>;
    setXml(xml: string): APIResult;
    getInfo(): APIResult<DiagramInfo>;
    getPages(): APIResult<PageData[]>;
    addPage(name?: string): APIResult<PageData>;
    removePage(pageId: string): APIResult;
    selectPage(pageId: string): APIResult;
    undo(): APIResult;
    redo(): APIResult;
    canUndo(): APIResult<boolean>;
    canRedo(): APIResult<boolean>;
    beginUpdate(): APIResult;
    endUpdate(): APIResult;
}

/**
 * @file CellManager.ts - Cell/Shape CRUD operations
 * @description Manages creation, modification, and deletion of cells (vertices and edges)
 */

declare class CellManager {
    private _api;
    constructor(api: DrawioAPI);
    private _buildStyleString;
    private _parseStyleString;
    insertVertex(options: VertexOptions): APIResult<{
        id: string;
    }>;
    insertEdge(options: EdgeOptions): APIResult<{
        id: string;
    }>;
    removeCell(cellId: string): APIResult;
    removeCells(cellIds: string[]): APIResult<{
        removed: number;
    }>;
    getCell(cellId: string): APIResult<CellData>;
    private _cellToData;
    getCells(): APIResult<CellData[]>;
    getVertices(): APIResult<CellData[]>;
    getEdges(): APIResult<CellData[]>;
    updateCell(cellId: string, updates: UpdateCellOptions): APIResult;
    moveCell(cellId: string, x: number, y: number): APIResult;
    resizeCell(cellId: string, width: number, height: number): APIResult;
    cloneCell(cellId: string, offsetX?: number, offsetY?: number): APIResult<{
        id: string;
    }>;
    groupCells(cellIds: string[]): APIResult<{
        id: string;
    }>;
    ungroupCells(groupId: string): APIResult<{
        ids: string[];
    }>;
    getParent(cellId: string): APIResult<CellData | null>;
    getChildren(cellId: string): APIResult<CellData[]>;
    getConnectedEdges(cellId: string, incoming?: boolean, outgoing?: boolean): APIResult<CellData[]>;
    getSelection(): APIResult<CellData[]>;
    setSelection(cellIds: string[]): APIResult;
    clearSelection(): APIResult;
    insertAwsIcon(options: AwsIconOptions): APIResult<{
        id: string;
    }>;
    insertAwsGroup(options: AwsGroupOptions): APIResult<{
        id: string;
    }>;
    getAwsGroupTypes(): APIResult<AwsGroupTypeInfo[]>;
    /**
     * Create a data URI from an SVG string.
     * @param svgContent - SVG content as string
     * @returns URL-encoded data URI
     */
    createSvgDataUri(svgContent: string): string;
    /**
     * Create a data URI from a PNG/JPG image buffer or base64 string.
     * @param imageData - Image data as Buffer or base64 string
     * @param mimeType - MIME type (default: 'image/png')
     * @returns Base64-encoded data URI
     */
    createImageDataUri(imageData: Buffer | string, mimeType?: string): string;
    /**
     * Insert a vertex with a custom image (SVG or raster).
     * @param options - Image vertex options
     * @returns API result with cell ID
     */
    insertImageVertex(options: {
        id?: string | null;
        label?: string;
        geometry: {
            x: number;
            y: number;
            width?: number;
            height?: number;
        };
        imageDataUri: string;
        maintainAspect?: boolean;
        styleOverrides?: CellStyle;
    }): APIResult<{
        id: string;
    }>;
}

/**
 * @file StyleManager.ts - Styling and formatting operations
 * @description Manages cell styles, default styles, and style manipulation
 */

declare class StyleManager {
    private _api;
    constructor(api: DrawioAPI);
    private _buildStyleString;
    private _parseStyleString;
    getStyle(cellId: string): APIResult<Record<string, string>>;
    setStyle(cellId: string, style: CellStyle): APIResult;
    updateStyle(cellId: string, updates: CellStyle): APIResult;
    getCellStyleString(cellId: string): APIResult<string>;
    setCellStyleString(cellId: string, styleString: string): APIResult;
    applyStyleToSelection(style: CellStyle): APIResult<{
        updated: number;
    }>;
    getDefaultVertexStyle(): APIResult<Record<string, unknown>>;
    getDefaultEdgeStyle(): APIResult<Record<string, unknown>>;
    setDefaultVertexStyle(style: CellStyle): APIResult;
    setDefaultEdgeStyle(style: CellStyle): APIResult;
    getComputedStyle(cellId: string): APIResult<Record<string, unknown>>;
    removeStyleProperties(cellId: string, properties: string[]): APIResult;
}

/**
 * @file IOManager.ts - Import/Export operations
 * @description Manages diagram serialization using XML format (native draw.io format)
 */

declare class IOManager {
    private _api;
    constructor(api: DrawioAPI);
    toXml(): APIResult<string>;
    fromXml(xml: string): APIResult;
    exportSvg(options?: SvgExportOptions): APIResult<string>;
    exportPng(options?: PngExportOptions): APIResult<string> | Promise<APIResult<string>>;
    importGraphML(xml: string): APIResult;
    toCompressedXml(): APIResult<string>;
    fromCompressedXml(data: string): APIResult;
    validateXml(xml: string): APIResult<XmlValidationResult>;
}

/**
 * @file LibraryManager.ts - Shape library management
 * @description Manages shape libraries (AWS4, Azure, GCP, etc.)
 */

declare const LIBRARIES: {
    readonly AWS4: "aws4";
};
declare class LibraryManager {
    private _api;
    private _libraries;
    constructor(api: DrawioAPI);
    getAvailableLibraries(): APIResult<LibraryInfo[]>;
    getLibraryInfo(libraryId: string): APIResult<LibraryInfo>;
    findIcon(libraryId: string, iconName: string, category?: string): APIResult<IconDefinition>;
    getIconsByCategory(libraryId: string, category: string): APIResult<Record<string, IconDefinition>>;
    getCategories(libraryId: string): APIResult<string[]>;
    getGroupTypes(libraryId: string): APIResult<string[]>;
    buildIconStyle(libraryId: string, iconName: string, options?: IconStyleOptions): APIResult<string>;
    buildGroupStyle(libraryId: string, groupType: string, options?: GroupStyleOptions$1): APIResult<string>;
    parseStyle(styleString: string): APIResult<Record<string, string>>;
    buildStyle(styleObj: Record<string, string | number>): APIResult<string>;
    getColors(libraryId: string): APIResult<Record<string, string>>;
    getAwsIcon(iconName: string, category?: string): APIResult<IconDefinition>;
    buildAwsIconStyle(iconName: string, options?: IconStyleOptions): APIResult<string>;
    buildAwsGroupStyle(groupType: string, options?: GroupStyleOptions$1): APIResult<string>;
}

/**
 * @file DrawioAPI.ts - Clean API Facade for draw.io
 * @description Provides programmatic control over draw.io diagrams.
 */

/**
 * Factory function to create a DrawioAPI instance.
 */
declare function createDrawioAPI(dependencies?: DrawioAPIDependencies): DrawioAPI;
/**
 * Main API class providing a facade over draw.io internals.
 */
declare class DrawioAPI {
    private _graph;
    private _model;
    private _editorUi;
    diagram: DiagramManager;
    cells: CellManager;
    styles: StyleManager;
    io: IOManager;
    libraries: LibraryManager;
    constructor(dependencies: DrawioAPIDependencies);
    /**
     * Initialize the API with an existing EditorUi instance.
     */
    init(editorUi: unknown): APIResult;
    /**
     * Check if the API is properly initialized.
     */
    isInitialized(): boolean;
    get graph(): unknown;
    get model(): unknown;
    get editorUi(): unknown;
    setGraph(graph: unknown): void;
    setModel(model: unknown): void;
    setEditorUi(editorUi: unknown): void;
    getVersion(): APIResult<{
        api: string;
        name: string;
    }>;
    /**
     * Execute an operation within a transaction.
     */
    transaction<T>(fn: () => T): APIResult<T>;
    insertVertex(options: VertexOptions): APIResult<{
        id: string;
    }>;
    insertEdge(options: EdgeOptions): APIResult<{
        id: string;
    }>;
    createSvgDataUri(svgContent: string): string;
    createImageDataUri(imageData: Buffer | string, mimeType?: string): string;
    insertImageVertex(options: {
        id?: string | null;
        label?: string;
        geometry: {
            x: number;
            y: number;
            width?: number;
            height?: number;
        };
        imageDataUri: string;
        maintainAspect?: boolean;
        styleOverrides?: Record<string, string | number | undefined>;
    }): APIResult<{
        id: string;
    }>;
    toXml(): APIResult<string>;
    fromXml(xml: string): APIResult;
}

declare class DiagramEngine {
    private _model;
    private _graph;
    private _api;
    private _filePath;
    private _diagramName;
    private _serializer;
    private _parser;
    constructor();
    create(options?: CreateDiagramOptions): APIResult<{
        name: string;
        isNew: boolean;
    }>;
    loadFromXml(xml: string): APIResult<{
        diagramName?: string;
        pageCount?: number;
    }>;
    loadFromFile(filePath: string): APIResult<{
        diagramName?: string;
        pageCount?: number;
    }>;
    toXml(options?: SerializeOptions): APIResult<string>;
    saveToFile(filePath?: string, options?: SerializeOptions): APIResult<{
        path: string;
        name: string;
    }>;
    getInfo(): APIResult<{
        name: string;
        filePath: string | null;
        cellCount?: number;
        vertexCount?: number;
        edgeCount?: number;
    }>;
    clear(): APIResult;
    get isLoaded(): boolean;
    get api(): DrawioAPI | null;
    get filePath(): string | null;
    get diagramName(): string;
    set diagramName(name: string);
}

declare class XmlParser {
    parse(xml: string, api: DrawioAPI): APIResult<ParseResult>;
    private _parseMxFile;
    private _getTextContent;
    private _decompress;
    private _parseMxGraphModel;
    private _parseVertex;
    private _parseEdge;
    private _parseStyleString;
}

/**
 * @file XmlSerializer.ts - Generate .drawio XML files
 * @description Serializes DrawioAPI model to valid .drawio XML format.
 */

declare class XmlSerializer {
    serialize(api: DrawioAPI, options?: SerializeOptions): APIResult<string>;
    private _serializeGraphModel;
    private _serializeCell;
    private _serializeVertex;
    private _serializeEdge;
    private _wrapInMxFile;
}

/**
 * @file MockModel.ts - Mock implementation of mxGraphModel
 * @description Provides a testable mock of mxGraphModel for unit testing
 */
interface MockCellInterface {
    id: string;
    children: MockCellInterface[];
    parent: MockCellInterface | null;
    value: string | null;
    geometry: MockGeometryInterface | null;
    style: string | null;
    vertex: boolean;
    edge: boolean;
    source: MockCellInterface | null;
    target: MockCellInterface | null;
    getId(): string;
    getValue(): string | null;
    setValue(v: string | null): void;
    getParent(): MockCellInterface | null;
    getGeometry(): MockGeometryInterface | null;
    setGeometry(g: MockGeometryInterface | null): void;
    getStyle(): string;
    setStyle(s: string): void;
    getChildCount(): number;
    getChildAt(i: number): MockCellInterface | null;
}
interface MockGeometryInterface {
    x: number;
    y: number;
    width: number;
    height: number;
    points?: Array<{
        x: number;
        y: number;
    }>;
    clone(): MockGeometryInterface;
}
declare class MockModel {
    private _nextId;
    private _updateLevel;
    private _cells;
    private _root;
    private _defaultParent;
    constructor();
    private _createRootCell;
    private _createDefaultParent;
    getRoot(): MockCellInterface;
    setRoot(root: MockCellInterface): void;
    getCell(id: string): MockCellInterface | null;
    getChildren(cell: MockCellInterface | null): MockCellInterface[];
    isVertex(cell: unknown): boolean;
    isEdge(cell: unknown): boolean;
    beginUpdate(): void;
    endUpdate(): void;
    getUpdateLevel(): number;
    clear(): void;
    add(parent: MockCellInterface, cell: MockCellInterface, index?: number): MockCellInterface;
    remove(cell: MockCellInterface): MockCellInterface;
    setValue(cell: MockCellInterface, value: string): void;
    setGeometry(cell: MockCellInterface, geometry: MockGeometryInterface): void;
    setStyle(cell: MockCellInterface, style: string): void;
    getNextId(): string;
}

/**
 * @file MockGraph.ts - Mock implementation of mxGraph
 * @description Provides a testable mock of mxGraph for unit testing
 */

interface MockStylesheet {
    getDefaultVertexStyle(): Record<string, unknown>;
    getDefaultEdgeStyle(): Record<string, unknown>;
}
interface MockGraphView {
    getState(cell: MockCellInterface): {
        style?: Record<string, unknown>;
    } | null;
    setState(cell: MockCellInterface, state: unknown): void;
}
declare class MockGraph {
    private _model;
    private _selection;
    private _stylesheet;
    private _view;
    constructor(model?: MockModel);
    getModel(): MockModel;
    getDefaultParent(): MockCellInterface;
    insertVertex(parent: MockCellInterface, id: string | null, value: string, x: number, y: number, width: number, height: number, style?: string): MockCellInterface;
    insertEdge(parent: MockCellInterface, id: string | null, value: string, source: MockCellInterface, target: MockCellInterface, style?: string): MockCellInterface;
    private _createCell;
    removeCells(cells: MockCellInterface[]): MockCellInterface[];
    cloneCells(cells: MockCellInterface[]): MockCellInterface[];
    addCells(cells: MockCellInterface[], parent: MockCellInterface): MockCellInterface[];
    groupCells(group: MockCellInterface | null, border: number, cells: MockCellInterface[]): MockCellInterface;
    ungroupCells(groups: MockCellInterface[]): MockCellInterface[];
    getEdges(cell: MockCellInterface, parent: MockCellInterface | null, incoming: boolean, outgoing: boolean): MockCellInterface[];
    getGraphBounds(): {
        x: number;
        y: number;
        width: number;
        height: number;
    } | null;
    getSelectionCells(): MockCellInterface[];
    setSelectionCells(cells: MockCellInterface[]): void;
    clearSelection(): void;
    getStylesheet(): MockStylesheet;
    getView(): MockGraphView;
    getSvg(): SVGElement | null;
}

/**
 * @file MockEditorUi.ts - Mock implementation of EditorUi
 * @description Provides a testable mock of EditorUi for unit testing
 */

declare class MockPage {
    private _id;
    private _name;
    constructor(id: string, name: string);
    getId(): string;
    getName(): string;
    setName(name: string): void;
}
declare class MockUndoManager {
    private _history;
    private _index;
    undo(): void;
    redo(): void;
    canUndo(): boolean;
    canRedo(): boolean;
    add(edit: unknown): void;
}
declare class MockEditorUi {
    private _graph;
    editor: {
        graph: MockGraph;
        undoManager: MockUndoManager;
    };
    pages: MockPage[];
    currentPage: MockPage;
    constructor(graph?: MockGraph);
    get graph(): MockGraph;
    insertPage(page: MockPage | null, index?: number): MockPage;
    removePage(page: MockPage): void;
    selectPage(page: MockPage): void;
    getFileData(compressed: boolean): string;
    setFileData(_data: string): void;
}

/**
 * @file AWS4Styles.ts - AWS4 icon style constants and builders
 * @description Provides style constants and builder functions for AWS4 icons.
 * Extracted from Sidebar-AWS4.js for programmatic use.
 */
/**
 * Icon definition for an AWS4 service icon.
 */
interface AWS4IconDefinition {
    name: string;
    icon: string;
    fillColor: string;
    width: number;
    height: number;
}
/**
 * Icon lookup result including category information.
 */
interface AWS4IconLookupResult extends AWS4IconDefinition {
    key: string;
    category: string;
}
/**
 * Group container definition for AWS4.
 */
interface AWS4GroupDefinition {
    name: string;
    grIcon?: string;
    strokeColor: string;
    fillColor: string;
    fontColor: string;
    dashed: boolean;
    simple?: boolean;
    grStroke?: number;
    centered?: boolean;
}
/**
 * Options for building resource icon styles.
 */
interface ResourceIconStyleOptions {
    fillColor?: string;
}
/**
 * Options for building product icon styles.
 */
interface ProductIconStyleOptions {
    fillColor?: string;
}
/**
 * Options for building group styles.
 */
interface GroupStyleOptions {
    strokeColor?: string;
    fillColor?: string;
    fontColor?: string;
}
/**
 * Style object parsed from style string.
 */
type StyleObject = Record<string, string | number | undefined>;
/**
 * AWS4 icon category with icon definitions.
 */
type AWS4IconCategory = Record<string, AWS4IconDefinition>;
/**
 * Base style patterns for AWS4 shapes.
 * These are the foundational style strings used to build AWS4 icon styles.
 */
declare const AWS4_BASE: {
    /**
     * Base style for resource icons (the main AWS service icons).
     * Used with resourceIcon shape type.
     */
    readonly RESOURCE_ICON: string;
    /**
     * Base style for product icons (simpler icons without the border).
     */
    readonly PRODUCT_ICON: string;
    /**
     * Base style for group containers (VPC, Region, Subnet, etc.).
     */
    readonly GROUP: string;
    /**
     * Base style for illustration icons.
     */
    readonly ILLUSTRATION: string;
};
/**
 * AWS service category colors.
 * These are the official AWS color codes for each service category.
 */
declare const AWS4_COLORS: {
    readonly analytics: "#8C4FFF";
    readonly applicationIntegration: "#E7157B";
    readonly blockchain: "#D45B07";
    readonly businessApplications: "#C925D1";
    readonly cloudFinancial: "#7AA116";
    readonly compute: "#ED7100";
    readonly contactCenter: "#E7157B";
    readonly containers: "#ED7100";
    readonly database: "#3B48CC";
    readonly developerTools: "#3B48CC";
    readonly endUserComputing: "#5F9EA0";
    readonly frontEndWebMobile: "#DD344C";
    readonly games: "#DD344C";
    readonly iot: "#7AA116";
    readonly machineLearning: "#01A88D";
    readonly managementGovernance: "#E7157B";
    readonly mediaServices: "#ED7100";
    readonly migration: "#7AA116";
    readonly networking: "#8C4FFF";
    readonly quantumTechnologies: "#8C4FFF";
    readonly robotics: "#DD344C";
    readonly satellite: "#8C4FFF";
    readonly security: "#DD344C";
    readonly serverless: "#ED7100";
    readonly storage: "#7AA116";
    readonly general: "#232F3D";
    readonly dark: "#1E262E";
    readonly white: "#ffffff";
    readonly gray: "#5A6C86";
};
/**
 * Comprehensive AWS4 icon catalog organized by category.
 * Each icon includes: name, icon identifier, fill color, and default dimensions.
 */
declare const AWS4_ICONS: Record<string, AWS4IconCategory>;
/**
 * AWS4 group/container style definitions.
 * Used for creating VPC, Region, Subnet, and other container shapes.
 */
declare const AWS4_GROUPS: Record<string, AWS4GroupDefinition>;
/**
 * Build a complete style string for an AWS4 resource icon.
 * @param iconName - Icon identifier (e.g., 'lambda', 'ec2', 's3')
 * @param options - Style options
 * @returns Complete style string for insertVertex
 */
declare function buildResourceIconStyle(iconName: string, options?: ResourceIconStyleOptions): string;
/**
 * Build a complete style string for an AWS4 product icon.
 * @param iconName - Icon identifier
 * @param options - Style options
 * @returns Complete style string for insertVertex
 */
declare function buildProductIconStyle(iconName: string, options?: ProductIconStyleOptions): string;
/**
 * Build a complete style string for an AWS4 group container.
 * @param groupType - Group type from AWS4_GROUPS (e.g., 'vpc', 'region')
 * @param options - Style options
 * @returns Complete style string for insertVertex
 */
declare function buildGroupStyle(groupType: string, options?: GroupStyleOptions): string;
/**
 * Look up an icon definition by name across all categories.
 * @param iconName - Icon name to find (case-insensitive)
 * @param category - Optional category hint for faster lookup
 * @returns Icon definition or null if not found
 */
declare function findIcon(iconName: string, category?: string): AWS4IconLookupResult | null;
/**
 * Get all available icon categories.
 * @returns Array of category names
 */
declare function getCategories(): string[];
/**
 * Get all icons in a specific category.
 * @param category - Category name
 * @returns Object with icon definitions or null if category not found
 */
declare function getIconsByCategory(category: string): AWS4IconCategory | null;
/**
 * Get all available group types.
 * @returns Array of group type names
 */
declare function getGroupTypes(): string[];
/**
 * Parse a style string into an object.
 * @param styleString - mxGraph style string
 * @returns Style object with key-value pairs
 */
declare function parseStyleString(styleString: string | null | undefined): StyleObject;
/**
 * Convert a style object to a style string.
 * @param styleObj - Style object
 * @returns mxGraph style string
 */
declare function buildStyleString(styleObj: StyleObject | null | undefined): string;

export { AWS4_BASE, AWS4_COLORS, AWS4_GROUPS, AWS4_ICONS, CellManager, DiagramEngine, DiagramManager, DrawioAPI, IOManager, LIBRARIES, LibraryManager, MockEditorUi, MockGraph, MockModel, MockPage, MockUndoManager, StyleManager, Types, XmlParser, XmlSerializer, buildGroupStyle, buildProductIconStyle, buildResourceIconStyle, buildStyleString, createDrawioAPI, findIcon, getCategories, getGroupTypes, getIconsByCategory, parseStyleString };
export type { APIResult, AwsGroupOptions, AwsGroupTypeInfo, AwsIconOptions, CellData, CellGeometry, CellStyle, CreateDiagramOptions, DiagramInfo, DrawioAPIDependencies, EdgeOptions, GroupDefinition, GroupStyleOptions$1 as GroupStyleOptions, IconDefinition, IconStyleOptions, LibraryInfo, MockCell, MockGeometry, PageData, ParseResult, PartialGeometry, PngExportOptions, Point, SerializeOptions, SvgExportOptions, UpdateCellOptions, VertexOptions, XmlValidationResult };
