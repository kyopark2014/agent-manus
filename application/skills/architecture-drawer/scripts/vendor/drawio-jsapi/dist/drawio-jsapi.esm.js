import { readFileSync, writeFileSync } from 'fs';
import { DOMParser } from '@xmldom/xmldom';
import pako from 'pako';

// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0
/**
 * Manages diagram-level operations including document lifecycle and pages.
 */
class DiagramManager {
    constructor(api) {
        this._api = api;
    }
    create() {
        try {
            const model = this._api.model;
            const graph = this._api.graph;
            if (!model || !graph) {
                return { success: false, error: "API not initialized" };
            }
            model.beginUpdate();
            try {
                model.clear();
                const root = new mxCell();
                root.setId("0");
                const defaultParent = new mxCell();
                defaultParent.setId("1");
                root.insert(defaultParent);
                model.setRoot(root);
            }
            finally {
                model.endUpdate();
            }
            return { success: true };
        }
        catch (e) {
            return { success: false, error: e.message };
        }
    }
    clear() {
        try {
            const model = this._api.model;
            const graph = this._api.graph;
            if (!model || !graph) {
                return { success: false, error: "API not initialized" };
            }
            model.beginUpdate();
            try {
                const parent = graph.getDefaultParent();
                const children = model.getChildren(parent);
                if (children && children.length > 0) {
                    graph.removeCells(children);
                }
            }
            finally {
                model.endUpdate();
            }
            return { success: true };
        }
        catch (e) {
            return { success: false, error: e.message };
        }
    }
    getXml() {
        try {
            const model = this._api.model;
            if (!model) {
                return { success: false, error: "API not initialized" };
            }
            const encoder = new mxCodec();
            const node = encoder.encode(model);
            const xml = mxUtils.getXml(node);
            return { success: true, data: xml };
        }
        catch (e) {
            return { success: false, error: e.message };
        }
    }
    setXml(xml) {
        try {
            const model = this._api.model;
            if (!model) {
                return { success: false, error: "API not initialized" };
            }
            if (!xml || typeof xml !== "string") {
                return { success: false, error: "Invalid XML input" };
            }
            const doc = mxUtils.parseXml(xml);
            const codec = new mxCodec(doc);
            model.beginUpdate();
            try {
                codec.decode(doc.documentElement, model);
            }
            finally {
                model.endUpdate();
            }
            return { success: true };
        }
        catch (e) {
            return { success: false, error: e.message };
        }
    }
    getInfo() {
        try {
            const model = this._api.model;
            const graph = this._api.graph;
            const ui = this._api.editorUi;
            if (!model || !graph) {
                return { success: false, error: "API not initialized" };
            }
            const parent = graph.getDefaultParent();
            const cells = model.getChildren(parent) || [];
            let vertexCount = 0;
            let edgeCount = 0;
            for (const cell of cells) {
                if (model.isVertex(cell)) {
                    vertexCount++;
                }
                else if (model.isEdge(cell)) {
                    edgeCount++;
                }
            }
            const info = {
                cellCount: cells.length,
                vertexCount,
                edgeCount,
                pageCount: ui && ui.pages ? ui.pages.length : 1,
                currentPageId: ui && ui.currentPage ? ui.currentPage.getId() : null,
            };
            return { success: true, data: info };
        }
        catch (e) {
            return { success: false, error: e.message };
        }
    }
    getPages() {
        try {
            const ui = this._api.editorUi;
            if (!ui) {
                return {
                    success: true,
                    data: [{ id: "1", name: "Page-1", index: 0 }],
                };
            }
            const pages = ui.pages || [];
            const pageData = pages.map((page, index) => ({
                id: page.getId(),
                name: page.getName(),
                index,
            }));
            return { success: true, data: pageData };
        }
        catch (e) {
            return { success: false, error: e.message };
        }
    }
    addPage(name) {
        try {
            const ui = this._api.editorUi;
            if (!ui || !ui.pages) {
                return { success: false, error: "Multi-page mode not available" };
            }
            const pageName = name || `Page-${ui.pages.length + 1}`;
            if (typeof ui.insertPage === "function") {
                const page = ui.insertPage(null, ui.pages.length);
                if (page) {
                    page.setName(pageName);
                    return {
                        success: true,
                        data: {
                            id: page.getId(),
                            name: pageName,
                            index: ui.pages.length - 1,
                        },
                    };
                }
            }
            return { success: false, error: "Page creation not supported" };
        }
        catch (e) {
            return { success: false, error: e.message };
        }
    }
    removePage(pageId) {
        try {
            const ui = this._api.editorUi;
            if (!ui || !ui.pages) {
                return { success: false, error: "Multi-page mode not available" };
            }
            if (ui.pages.length <= 1) {
                return { success: false, error: "Cannot remove the last page" };
            }
            const pageIndex = ui.pages.findIndex((p) => p.getId() === pageId);
            if (pageIndex === -1) {
                return { success: false, error: "Page not found" };
            }
            if (typeof ui.removePage === "function") {
                ui.removePage(ui.pages[pageIndex]);
                return { success: true };
            }
            return { success: false, error: "Page removal not supported" };
        }
        catch (e) {
            return { success: false, error: e.message };
        }
    }
    selectPage(pageId) {
        try {
            const ui = this._api.editorUi;
            if (!ui || !ui.pages) {
                return { success: false, error: "Multi-page mode not available" };
            }
            const page = ui.pages.find((p) => p.getId() === pageId);
            if (!page) {
                return { success: false, error: "Page not found" };
            }
            if (typeof ui.selectPage === "function") {
                ui.selectPage(page);
                return { success: true };
            }
            return { success: false, error: "Page selection not supported" };
        }
        catch (e) {
            return { success: false, error: e.message };
        }
    }
    undo() {
        try {
            const ui = this._api.editorUi;
            if (ui && ui.editor && ui.editor.undoManager) {
                ui.editor.undoManager.undo();
                return { success: true };
            }
            return { success: false, error: "Undo not available" };
        }
        catch (e) {
            return { success: false, error: e.message };
        }
    }
    redo() {
        try {
            const ui = this._api.editorUi;
            if (ui && ui.editor && ui.editor.undoManager) {
                ui.editor.undoManager.redo();
                return { success: true };
            }
            return { success: false, error: "Redo not available" };
        }
        catch (e) {
            return { success: false, error: e.message };
        }
    }
    canUndo() {
        try {
            const ui = this._api.editorUi;
            if (ui && ui.editor && ui.editor.undoManager) {
                return { success: true, data: ui.editor.undoManager.canUndo() };
            }
            return { success: true, data: false };
        }
        catch (e) {
            return { success: false, error: e.message };
        }
    }
    canRedo() {
        try {
            const ui = this._api.editorUi;
            if (ui && ui.editor && ui.editor.undoManager) {
                return { success: true, data: ui.editor.undoManager.canRedo() };
            }
            return { success: true, data: false };
        }
        catch (e) {
            return { success: false, error: e.message };
        }
    }
    beginUpdate() {
        try {
            const model = this._api.model;
            if (!model) {
                return { success: false, error: "API not initialized" };
            }
            model.beginUpdate();
            return { success: true };
        }
        catch (e) {
            return { success: false, error: e.message };
        }
    }
    endUpdate() {
        try {
            const model = this._api.model;
            if (!model) {
                return { success: false, error: "API not initialized" };
            }
            model.endUpdate();
            return { success: true };
        }
        catch (e) {
            return { success: false, error: e.message };
        }
    }
}

// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0
// ============================================================================
// BASE STYLES
// ============================================================================
/**
 * Base style patterns for AWS4 shapes.
 * These are the foundational style strings used to build AWS4 icon styles.
 */
const AWS4_BASE = {
    /**
     * Base style for resource icons (the main AWS service icons).
     * Used with resourceIcon shape type.
     */
    RESOURCE_ICON: "sketch=0;points=[[0,0,0],[0.25,0,0],[0.5,0,0],[0.75,0,0],[1,0,0]," +
        "[0,1,0],[0.25,1,0],[0.5,1,0],[0.75,1,0],[1,1,0],[0,0.25,0],[0,0.5,0]," +
        "[0,0.75,0],[1,0.25,0],[1,0.5,0],[1,0.75,0]];outlineConnect=0;fontColor=#232F3E;" +
        "strokeColor=#ffffff;dashed=0;verticalLabelPosition=bottom;verticalAlign=top;" +
        "align=center;html=1;fontSize=12;fontStyle=0;aspect=fixed;shape=mxgraph.aws4.",
    /**
     * Base style for product icons (simpler icons without the border).
     */
    PRODUCT_ICON: "sketch=0;outlineConnect=0;fontColor=#232F3E;gradientColor=none;" +
        "strokeColor=none;dashed=0;verticalLabelPosition=bottom;verticalAlign=top;" +
        "align=center;html=1;fontSize=12;fontStyle=0;aspect=fixed;pointerEvents=1;shape=mxgraph.aws4.",
    /**
     * Base style for group containers (VPC, Region, Subnet, etc.).
     */
    GROUP: "points=[[0,0],[0.25,0],[0.5,0],[0.75,0],[1,0],[1,0.25],[1,0.5],[1,0.75]," +
        "[1,1],[0.75,1],[0.5,1],[0.25,1],[0,1],[0,0.75],[0,0.5],[0,0.25]];" +
        "outlineConnect=0;gradientColor=none;html=1;whiteSpace=wrap;fontSize=12;" +
        "fontStyle=0;container=1;pointerEvents=0;collapsible=0;recursiveResize=0;" +
        "shape=mxgraph.aws4.",
    /**
     * Base style for illustration icons.
     */
    ILLUSTRATION: "sketch=0;outlineConnect=0;gradientColor=none;fontColor=#545B64;" +
        "strokeColor=none;fillColor=#879196;dashed=0;verticalLabelPosition=bottom;" +
        "verticalAlign=top;align=center;html=1;fontSize=12;fontStyle=0;aspect=fixed;shape=mxgraph.aws4.",
};
// ============================================================================
// COLORS
// ============================================================================
/**
 * AWS service category colors.
 * These are the official AWS color codes for each service category.
 */
const AWS4_COLORS = {
    // Category colors
    analytics: "#8C4FFF",
    applicationIntegration: "#E7157B",
    blockchain: "#D45B07",
    businessApplications: "#C925D1",
    cloudFinancial: "#7AA116",
    compute: "#ED7100",
    contactCenter: "#E7157B",
    containers: "#ED7100",
    database: "#3B48CC",
    developerTools: "#3B48CC",
    endUserComputing: "#5F9EA0",
    frontEndWebMobile: "#DD344C",
    games: "#DD344C",
    iot: "#7AA116",
    machineLearning: "#01A88D",
    managementGovernance: "#E7157B",
    mediaServices: "#ED7100",
    migration: "#7AA116",
    networking: "#8C4FFF",
    quantumTechnologies: "#8C4FFF",
    robotics: "#DD344C",
    satellite: "#8C4FFF",
    security: "#DD344C",
    serverless: "#ED7100",
    storage: "#7AA116",
    // General colors
    general: "#232F3D",
    dark: "#1E262E",
    white: "#ffffff",
    gray: "#5A6C86",
};
// ============================================================================
// ICONS
// ============================================================================
/**
 * Comprehensive AWS4 icon catalog organized by category.
 * Each icon includes: name, icon identifier, fill color, and default dimensions.
 */
const AWS4_ICONS = {
    // ============================================================================
    // COMPUTE
    // ============================================================================
    compute: {
        ec2: {
            name: "EC2",
            icon: "ec2",
            fillColor: "#ED7100",
            width: 78,
            height: 78,
        },
        lambda: {
            name: "Lambda",
            icon: "lambda",
            fillColor: "#ED7100",
            width: 78,
            height: 78,
        },
        ecs: {
            name: "ECS",
            icon: "ecs",
            fillColor: "#ED7100",
            width: 78,
            height: 78,
        },
        eks: {
            name: "EKS",
            icon: "eks",
            fillColor: "#ED7100",
            width: 78,
            height: 78,
        },
        fargate: {
            name: "Fargate",
            icon: "fargate",
            fillColor: "#ED7100",
            width: 78,
            height: 78,
        },
        batch: {
            name: "Batch",
            icon: "batch",
            fillColor: "#ED7100",
            width: 78,
            height: 78,
        },
        elasticBeanstalk: {
            name: "Elastic Beanstalk",
            icon: "elastic_beanstalk",
            fillColor: "#ED7100",
            width: 78,
            height: 78,
        },
        lightsail: {
            name: "Lightsail",
            icon: "lightsail",
            fillColor: "#ED7100",
            width: 78,
            height: 78,
        },
        outposts: {
            name: "Outposts",
            icon: "outposts",
            fillColor: "#ED7100",
            width: 78,
            height: 78,
        },
        serverlessApplicationRepository: {
            name: "SAR",
            icon: "serverless_application_repository",
            fillColor: "#ED7100",
            width: 78,
            height: 78,
        },
        wavelength: {
            name: "Wavelength",
            icon: "wavelength",
            fillColor: "#ED7100",
            width: 78,
            height: 78,
        },
        localZones: {
            name: "Local Zones",
            icon: "local_zones",
            fillColor: "#ED7100",
            width: 78,
            height: 78,
        },
        appRunner: {
            name: "App Runner",
            icon: "app_runner",
            fillColor: "#ED7100",
            width: 78,
            height: 78,
        },
        // EC2 instance types
        ec2Instance: {
            name: "EC2 Instance",
            icon: "instance",
            fillColor: "#ED7100",
            width: 78,
            height: 78,
        },
        ec2Instances: {
            name: "EC2 Instances",
            icon: "instances",
            fillColor: "#ED7100",
            width: 78,
            height: 78,
        },
        ec2Ami: {
            name: "AMI",
            icon: "ami",
            fillColor: "#ED7100",
            width: 78,
            height: 78,
        },
        ec2AutoScaling: {
            name: "Auto Scaling",
            icon: "auto_scaling2",
            fillColor: "#ED7100",
            width: 78,
            height: 78,
        },
        elasticIpAddress: {
            name: "Elastic IP",
            icon: "elastic_ip_address",
            fillColor: "#ED7100",
            width: 78,
            height: 78,
        },
        spotInstance: {
            name: "Spot Instance",
            icon: "spot_instance",
            fillColor: "#ED7100",
            width: 78,
            height: 78,
        },
    },
    // ============================================================================
    // DATABASE
    // ============================================================================
    database: {
        rds: {
            name: "RDS",
            icon: "rds",
            fillColor: "#3B48CC",
            width: 78,
            height: 78,
        },
        aurora: {
            name: "Aurora",
            icon: "aurora",
            fillColor: "#3B48CC",
            width: 78,
            height: 78,
        },
        dynamodb: {
            name: "DynamoDB",
            icon: "dynamodb",
            fillColor: "#3B48CC",
            width: 78,
            height: 78,
        },
        elasticache: {
            name: "ElastiCache",
            icon: "elasticache",
            fillColor: "#3B48CC",
            width: 78,
            height: 78,
        },
        neptune: {
            name: "Neptune",
            icon: "neptune",
            fillColor: "#3B48CC",
            width: 78,
            height: 78,
        },
        redshift: {
            name: "Redshift",
            icon: "redshift",
            fillColor: "#8C4FFF",
            width: 78,
            height: 78,
        },
        documentdb: {
            name: "DocumentDB",
            icon: "documentdb",
            fillColor: "#3B48CC",
            width: 78,
            height: 78,
        },
        keyspaces: {
            name: "Keyspaces",
            icon: "keyspaces",
            fillColor: "#3B48CC",
            width: 78,
            height: 78,
        },
        qldb: {
            name: "QLDB",
            icon: "qldb",
            fillColor: "#3B48CC",
            width: 78,
            height: 78,
        },
        timestream: {
            name: "Timestream",
            icon: "timestream",
            fillColor: "#3B48CC",
            width: 78,
            height: 78,
        },
        memorydb: {
            name: "MemoryDB",
            icon: "memorydb",
            fillColor: "#3B48CC",
            width: 78,
            height: 78,
        },
        // Database specific icons
        rdsInstance: {
            name: "RDS Instance",
            icon: "rds_instance",
            fillColor: "#3B48CC",
            width: 78,
            height: 78,
        },
        rdsMysql: {
            name: "RDS MySQL",
            icon: "rds_mysql_instance",
            fillColor: "#3B48CC",
            width: 78,
            height: 78,
        },
        rdsPostgresql: {
            name: "RDS PostgreSQL",
            icon: "rds_postgresql_instance",
            fillColor: "#3B48CC",
            width: 78,
            height: 78,
        },
        dynamodbTable: {
            name: "DynamoDB Table",
            icon: "table",
            fillColor: "#3B48CC",
            width: 78,
            height: 78,
        },
        dynamodbItems: {
            name: "DynamoDB Items",
            icon: "items",
            fillColor: "#3B48CC",
            width: 78,
            height: 78,
        },
        dynamodbAttribute: {
            name: "DynamoDB Attribute",
            icon: "attribute",
            fillColor: "#3B48CC",
            width: 78,
            height: 78,
        },
    },
    // ============================================================================
    // STORAGE
    // ============================================================================
    storage: {
        s3: { name: "S3", icon: "s3", fillColor: "#7AA116", width: 78, height: 78 },
        efs: {
            name: "EFS",
            icon: "elastic_file_system",
            fillColor: "#7AA116",
            width: 78,
            height: 78,
        },
        ebs: {
            name: "EBS",
            icon: "elastic_block_store",
            fillColor: "#7AA116",
            width: 78,
            height: 78,
        },
        fsx: {
            name: "FSx",
            icon: "fsx",
            fillColor: "#7AA116",
            width: 78,
            height: 78,
        },
        glacier: {
            name: "S3 Glacier",
            icon: "s3_glacier",
            fillColor: "#7AA116",
            width: 78,
            height: 78,
        },
        storageGateway: {
            name: "Storage Gateway",
            icon: "storage_gateway",
            fillColor: "#7AA116",
            width: 78,
            height: 78,
        },
        backup: {
            name: "Backup",
            icon: "backup",
            fillColor: "#7AA116",
            width: 78,
            height: 78,
        },
        snowball: {
            name: "Snowball",
            icon: "snowball",
            fillColor: "#7AA116",
            width: 78,
            height: 78,
        },
        snowballEdge: {
            name: "Snowball Edge",
            icon: "snowball_edge",
            fillColor: "#7AA116",
            width: 78,
            height: 78,
        },
        snowcone: {
            name: "Snowcone",
            icon: "snowcone",
            fillColor: "#7AA116",
            width: 78,
            height: 78,
        },
        snowmobile: {
            name: "Snowmobile",
            icon: "snowmobile",
            fillColor: "#7AA116",
            width: 78,
            height: 78,
        },
        // S3 specific icons
        s3Bucket: {
            name: "S3 Bucket",
            icon: "bucket",
            fillColor: "#7AA116",
            width: 78,
            height: 78,
        },
        s3BucketWithObjects: {
            name: "S3 Bucket Objects",
            icon: "bucket_with_objects",
            fillColor: "#7AA116",
            width: 78,
            height: 78,
        },
        s3Object: {
            name: "S3 Object",
            icon: "object",
            fillColor: "#7AA116",
            width: 78,
            height: 78,
        },
        s3GlacierArchive: {
            name: "Glacier Archive",
            icon: "archive",
            fillColor: "#7AA116",
            width: 78,
            height: 78,
        },
        s3GlacierVault: {
            name: "Glacier Vault",
            icon: "vault",
            fillColor: "#7AA116",
            width: 78,
            height: 78,
        },
    },
    // ============================================================================
    // NETWORKING
    // ============================================================================
    networking: {
        vpc: {
            name: "VPC",
            icon: "vpc",
            fillColor: "#8C4FFF",
            width: 78,
            height: 78,
        },
        cloudfront: {
            name: "CloudFront",
            icon: "cloudfront",
            fillColor: "#8C4FFF",
            width: 78,
            height: 78,
        },
        route53: {
            name: "Route 53",
            icon: "route_53",
            fillColor: "#8C4FFF",
            width: 78,
            height: 78,
        },
        apiGateway: {
            name: "API Gateway",
            icon: "api_gateway",
            fillColor: "#E7157B",
            width: 78,
            height: 78,
        },
        directConnect: {
            name: "Direct Connect",
            icon: "direct_connect",
            fillColor: "#8C4FFF",
            width: 78,
            height: 78,
        },
        globalAccelerator: {
            name: "Global Accelerator",
            icon: "global_accelerator",
            fillColor: "#8C4FFF",
            width: 78,
            height: 78,
        },
        transitGateway: {
            name: "Transit Gateway",
            icon: "transit_gateway",
            fillColor: "#8C4FFF",
            width: 78,
            height: 78,
        },
        elb: {
            name: "ELB",
            icon: "elastic_load_balancing",
            fillColor: "#8C4FFF",
            width: 78,
            height: 78,
        },
        privateLink: {
            name: "PrivateLink",
            icon: "privatelink",
            fillColor: "#8C4FFF",
            width: 78,
            height: 78,
        },
        appMesh: {
            name: "App Mesh",
            icon: "app_mesh",
            fillColor: "#8C4FFF",
            width: 78,
            height: 78,
        },
        cloudMap: {
            name: "Cloud Map",
            icon: "cloud_map",
            fillColor: "#8C4FFF",
            width: 78,
            height: 78,
        },
        // VPC specific icons
        internetGateway: {
            name: "Internet Gateway",
            icon: "internet_gateway",
            fillColor: "#8C4FFF",
            width: 78,
            height: 78,
        },
        natGateway: {
            name: "NAT Gateway",
            icon: "nat_gateway",
            fillColor: "#8C4FFF",
            width: 78,
            height: 78,
        },
        vpnGateway: {
            name: "VPN Gateway",
            icon: "vpn_gateway",
            fillColor: "#8C4FFF",
            width: 78,
            height: 78,
        },
        customerGateway: {
            name: "Customer Gateway",
            icon: "customer_gateway",
            fillColor: "#8C4FFF",
            width: 78,
            height: 78,
        },
        vpnConnection: {
            name: "VPN Connection",
            icon: "vpn_connection",
            fillColor: "#8C4FFF",
            width: 78,
            height: 78,
        },
        routeTable: {
            name: "Route Table",
            icon: "route_table",
            fillColor: "#8C4FFF",
            width: 78,
            height: 78,
        },
        networkAcl: {
            name: "Network ACL",
            icon: "network_access_control_list",
            fillColor: "#8C4FFF",
            width: 78,
            height: 78,
        },
        securityGroup: {
            name: "Security Group",
            icon: "security_group",
            fillColor: "#8C4FFF",
            width: 78,
            height: 78,
        },
        elasticNetworkInterface: {
            name: "ENI",
            icon: "elastic_network_interface",
            fillColor: "#8C4FFF",
            width: 78,
            height: 78,
        },
        endpoints: {
            name: "Endpoints",
            icon: "endpoints",
            fillColor: "#8C4FFF",
            width: 78,
            height: 78,
        },
        // Load balancer types
        applicationLoadBalancer: {
            name: "ALB",
            icon: "application_load_balancer",
            fillColor: "#8C4FFF",
            width: 78,
            height: 78,
        },
        networkLoadBalancer: {
            name: "NLB",
            icon: "network_load_balancer",
            fillColor: "#8C4FFF",
            width: 78,
            height: 78,
        },
        classicLoadBalancer: {
            name: "CLB",
            icon: "classic_load_balancer",
            fillColor: "#8C4FFF",
            width: 78,
            height: 78,
        },
        gatewayLoadBalancer: {
            name: "GWLB",
            icon: "gateway_load_balancer",
            fillColor: "#8C4FFF",
            width: 78,
            height: 78,
        },
    },
    // ============================================================================
    // SECURITY
    // ============================================================================
    security: {
        iam: {
            name: "IAM",
            icon: "iam",
            fillColor: "#DD344C",
            width: 78,
            height: 78,
        },
        cognito: {
            name: "Cognito",
            icon: "cognito",
            fillColor: "#DD344C",
            width: 78,
            height: 78,
        },
        secretsManager: {
            name: "Secrets Manager",
            icon: "secrets_manager",
            fillColor: "#DD344C",
            width: 78,
            height: 78,
        },
        kms: {
            name: "KMS",
            icon: "key_management_service",
            fillColor: "#DD344C",
            width: 78,
            height: 78,
        },
        shield: {
            name: "Shield",
            icon: "shield",
            fillColor: "#DD344C",
            width: 78,
            height: 78,
        },
        waf: {
            name: "WAF",
            icon: "waf",
            fillColor: "#DD344C",
            width: 78,
            height: 78,
        },
        guardDuty: {
            name: "GuardDuty",
            icon: "guardduty",
            fillColor: "#DD344C",
            width: 78,
            height: 78,
        },
        inspector: {
            name: "Inspector",
            icon: "inspector",
            fillColor: "#DD344C",
            width: 78,
            height: 78,
        },
        macie: {
            name: "Macie",
            icon: "macie",
            fillColor: "#DD344C",
            width: 78,
            height: 78,
        },
        securityHub: {
            name: "Security Hub",
            icon: "security_hub",
            fillColor: "#DD344C",
            width: 78,
            height: 78,
        },
        detective: {
            name: "Detective",
            icon: "detective",
            fillColor: "#DD344C",
            width: 78,
            height: 78,
        },
        firewall: {
            name: "Network Firewall",
            icon: "network_firewall",
            fillColor: "#DD344C",
            width: 78,
            height: 78,
        },
        firewallManager: {
            name: "Firewall Manager",
            icon: "firewall_manager",
            fillColor: "#DD344C",
            width: 78,
            height: 78,
        },
        certificateManager: {
            name: "ACM",
            icon: "certificate_manager",
            fillColor: "#DD344C",
            width: 78,
            height: 78,
        },
        cloudhsm: {
            name: "CloudHSM",
            icon: "cloudhsm",
            fillColor: "#DD344C",
            width: 78,
            height: 78,
        },
        directoryService: {
            name: "Directory Service",
            icon: "directory_service",
            fillColor: "#DD344C",
            width: 78,
            height: 78,
        },
        sso: {
            name: "IAM Identity Center",
            icon: "single_sign_on",
            fillColor: "#DD344C",
            width: 78,
            height: 78,
        },
        ram: {
            name: "RAM",
            icon: "resource_access_manager",
            fillColor: "#DD344C",
            width: 78,
            height: 78,
        },
        artifact: {
            name: "Artifact",
            icon: "artifact",
            fillColor: "#DD344C",
            width: 78,
            height: 78,
        },
        auditManager: {
            name: "Audit Manager",
            icon: "audit_manager",
            fillColor: "#DD344C",
            width: 78,
            height: 78,
        },
        signer: {
            name: "Signer",
            icon: "signer",
            fillColor: "#DD344C",
            width: 78,
            height: 78,
        },
        // IAM specific
        iamRole: {
            name: "IAM Role",
            icon: "role",
            fillColor: "#DD344C",
            width: 78,
            height: 78,
        },
        iamPermissions: {
            name: "IAM Permissions",
            icon: "permissions",
            fillColor: "#DD344C",
            width: 78,
            height: 78,
        },
        iamDataEncryptionKey: {
            name: "Data Encryption Key",
            icon: "data_encryption_key",
            fillColor: "#DD344C",
            width: 78,
            height: 78,
        },
    },
    // ============================================================================
    // APPLICATION INTEGRATION
    // ============================================================================
    applicationIntegration: {
        sns: {
            name: "SNS",
            icon: "sns",
            fillColor: "#E7157B",
            width: 78,
            height: 78,
        },
        sqs: {
            name: "SQS",
            icon: "sqs",
            fillColor: "#E7157B",
            width: 78,
            height: 78,
        },
        eventBridge: {
            name: "EventBridge",
            icon: "eventbridge",
            fillColor: "#E7157B",
            width: 78,
            height: 78,
        },
        stepFunctions: {
            name: "Step Functions",
            icon: "step_functions",
            fillColor: "#E7157B",
            width: 78,
            height: 78,
        },
        appSync: {
            name: "AppSync",
            icon: "appsync",
            fillColor: "#E7157B",
            width: 78,
            height: 78,
        },
        mq: { name: "MQ", icon: "mq", fillColor: "#E7157B", width: 78, height: 78 },
        appFlow: {
            name: "AppFlow",
            icon: "appflow",
            fillColor: "#E7157B",
            width: 78,
            height: 78,
        },
        managedWorkflows: {
            name: "Managed Workflows",
            icon: "managed_workflows_for_apache_airflow",
            fillColor: "#E7157B",
            width: 78,
            height: 78,
        },
        // SNS/SQS specific
        snsTopic: {
            name: "SNS Topic",
            icon: "topic",
            fillColor: "#E7157B",
            width: 78,
            height: 78,
        },
        snsEmailNotification: {
            name: "Email Notification",
            icon: "email_notification",
            fillColor: "#E7157B",
            width: 78,
            height: 78,
        },
        sqsQueue: {
            name: "SQS Queue",
            icon: "queue",
            fillColor: "#E7157B",
            width: 78,
            height: 78,
        },
        sqsMessage: {
            name: "SQS Message",
            icon: "message",
            fillColor: "#E7157B",
            width: 78,
            height: 78,
        },
    },
    // ============================================================================
    // ANALYTICS
    // ============================================================================
    analytics: {
        athena: {
            name: "Athena",
            icon: "athena",
            fillColor: "#8C4FFF",
            width: 78,
            height: 78,
        },
        emr: {
            name: "EMR",
            icon: "emr",
            fillColor: "#8C4FFF",
            width: 78,
            height: 78,
        },
        kinesis: {
            name: "Kinesis",
            icon: "kinesis",
            fillColor: "#8C4FFF",
            width: 78,
            height: 78,
        },
        kinesisDataStreams: {
            name: "Kinesis Data Streams",
            icon: "kinesis_data_streams",
            fillColor: "#8C4FFF",
            width: 78,
            height: 78,
        },
        kinesisDataFirehose: {
            name: "Kinesis Firehose",
            icon: "kinesis_data_firehose",
            fillColor: "#8C4FFF",
            width: 78,
            height: 78,
        },
        kinesisDataAnalytics: {
            name: "Kinesis Analytics",
            icon: "kinesis_data_analytics",
            fillColor: "#8C4FFF",
            width: 78,
            height: 78,
        },
        kinesisVideoStreams: {
            name: "Kinesis Video",
            icon: "kinesis_video_streams",
            fillColor: "#8C4FFF",
            width: 78,
            height: 78,
        },
        glue: {
            name: "Glue",
            icon: "glue",
            fillColor: "#8C4FFF",
            width: 78,
            height: 78,
        },
        glueDataBrew: {
            name: "Glue DataBrew",
            icon: "glue_databrew",
            fillColor: "#8C4FFF",
            width: 78,
            height: 78,
        },
        lakeFormation: {
            name: "Lake Formation",
            icon: "lake_formation",
            fillColor: "#8C4FFF",
            width: 78,
            height: 78,
        },
        quickSight: {
            name: "QuickSight",
            icon: "quicksight",
            fillColor: "#8C4FFF",
            width: 78,
            height: 78,
        },
        dataExchange: {
            name: "Data Exchange",
            icon: "data_exchange",
            fillColor: "#8C4FFF",
            width: 78,
            height: 78,
        },
        dataPipeline: {
            name: "Data Pipeline",
            icon: "data_pipeline",
            fillColor: "#8C4FFF",
            width: 78,
            height: 78,
        },
        openSearch: {
            name: "OpenSearch",
            icon: "elasticsearch_service",
            fillColor: "#8C4FFF",
            width: 78,
            height: 78,
        },
        cloudSearch: {
            name: "CloudSearch",
            icon: "cloudsearch2",
            fillColor: "#8C4FFF",
            width: 78,
            height: 78,
        },
        msk: {
            name: "MSK",
            icon: "managed_streaming_for_kafka",
            fillColor: "#8C4FFF",
            width: 78,
            height: 78,
        },
    },
    // ============================================================================
    // MANAGEMENT & GOVERNANCE
    // ============================================================================
    managementGovernance: {
        cloudWatch: {
            name: "CloudWatch",
            icon: "cloudwatch",
            fillColor: "#E7157B",
            width: 78,
            height: 78,
        },
        cloudTrail: {
            name: "CloudTrail",
            icon: "cloudtrail",
            fillColor: "#E7157B",
            width: 78,
            height: 78,
        },
        config: {
            name: "Config",
            icon: "config",
            fillColor: "#E7157B",
            width: 78,
            height: 78,
        },
        cloudFormation: {
            name: "CloudFormation",
            icon: "cloudformation",
            fillColor: "#E7157B",
            width: 78,
            height: 78,
        },
        systemsManager: {
            name: "Systems Manager",
            icon: "systems_manager",
            fillColor: "#E7157B",
            width: 78,
            height: 78,
        },
        serviceCatalog: {
            name: "Service Catalog",
            icon: "service_catalog",
            fillColor: "#E7157B",
            width: 78,
            height: 78,
        },
        trustedAdvisor: {
            name: "Trusted Advisor",
            icon: "trusted_advisor",
            fillColor: "#E7157B",
            width: 78,
            height: 78,
        },
        controlTower: {
            name: "Control Tower",
            icon: "control_tower",
            fillColor: "#E7157B",
            width: 78,
            height: 78,
        },
        organizations: {
            name: "Organizations",
            icon: "organizations",
            fillColor: "#E7157B",
            width: 78,
            height: 78,
        },
        opsWorks: {
            name: "OpsWorks",
            icon: "opsworks",
            fillColor: "#E7157B",
            width: 78,
            height: 78,
        },
        licenseManager: {
            name: "License Manager",
            icon: "license_manager",
            fillColor: "#E7157B",
            width: 78,
            height: 78,
        },
        wellArchitected: {
            name: "Well-Architected",
            icon: "well_architected_tool",
            fillColor: "#E7157B",
            width: 78,
            height: 78,
        },
        personalHealthDashboard: {
            name: "Health Dashboard",
            icon: "personal_health_dashboard",
            fillColor: "#E7157B",
            width: 78,
            height: 78,
        },
        managementConsole: {
            name: "Management Console",
            icon: "management_console",
            fillColor: "#E7157B",
            width: 78,
            height: 78,
        },
        appConfig: {
            name: "AppConfig",
            icon: "appconfig",
            fillColor: "#E7157B",
            width: 78,
            height: 78,
        },
        // CloudWatch specific
        cloudWatchAlarm: {
            name: "CloudWatch Alarm",
            icon: "alarm",
            fillColor: "#E7157B",
            width: 78,
            height: 78,
        },
        cloudWatchRule: {
            name: "CloudWatch Rule",
            icon: "rule",
            fillColor: "#E7157B",
            width: 78,
            height: 78,
        },
        cloudWatchLogs: {
            name: "CloudWatch Logs",
            icon: "logs",
            fillColor: "#E7157B",
            width: 78,
            height: 78,
        },
    },
    // ============================================================================
    // DEVELOPER TOOLS
    // ============================================================================
    developerTools: {
        codeCommit: {
            name: "CodeCommit",
            icon: "codecommit",
            fillColor: "#3B48CC",
            width: 78,
            height: 78,
        },
        codeBuild: {
            name: "CodeBuild",
            icon: "codebuild",
            fillColor: "#3B48CC",
            width: 78,
            height: 78,
        },
        codeDeploy: {
            name: "CodeDeploy",
            icon: "codedeploy",
            fillColor: "#3B48CC",
            width: 78,
            height: 78,
        },
        codePipeline: {
            name: "CodePipeline",
            icon: "codepipeline",
            fillColor: "#3B48CC",
            width: 78,
            height: 78,
        },
        codeArtifact: {
            name: "CodeArtifact",
            icon: "codeartifact",
            fillColor: "#3B48CC",
            width: 78,
            height: 78,
        },
        codeStar: {
            name: "CodeStar",
            icon: "codestar",
            fillColor: "#3B48CC",
            width: 78,
            height: 78,
        },
        cloud9: {
            name: "Cloud9",
            icon: "cloud9",
            fillColor: "#3B48CC",
            width: 78,
            height: 78,
        },
        xRay: {
            name: "X-Ray",
            icon: "xray",
            fillColor: "#3B48CC",
            width: 78,
            height: 78,
        },
        cli: {
            name: "CLI",
            icon: "command_line_interface",
            fillColor: "#3B48CC",
            width: 78,
            height: 78,
        },
        toolsAndSdks: {
            name: "Tools and SDKs",
            icon: "tools_and_sdks",
            fillColor: "#3B48CC",
            width: 78,
            height: 78,
        },
    },
    // ============================================================================
    // MACHINE LEARNING / AI
    // ============================================================================
    machineLearning: {
        sagemaker: {
            name: "SageMaker",
            icon: "sagemaker",
            fillColor: "#01A88D",
            width: 78,
            height: 78,
        },
        sagemaker2: {
            name: "SageMaker",
            icon: "sagemaker_2",
            fillColor: "#01A88D",
            width: 78,
            height: 78,
        },
        rekognition: {
            name: "Rekognition",
            icon: "rekognition",
            fillColor: "#01A88D",
            width: 78,
            height: 78,
        },
        polly: {
            name: "Polly",
            icon: "polly",
            fillColor: "#01A88D",
            width: 78,
            height: 78,
        },
        lex: {
            name: "Lex",
            icon: "lex",
            fillColor: "#01A88D",
            width: 78,
            height: 78,
        },
        transcribe: {
            name: "Transcribe",
            icon: "transcribe",
            fillColor: "#01A88D",
            width: 78,
            height: 78,
        },
        translate: {
            name: "Translate",
            icon: "translate",
            fillColor: "#01A88D",
            width: 78,
            height: 78,
        },
        comprehend: {
            name: "Comprehend",
            icon: "comprehend",
            fillColor: "#01A88D",
            width: 78,
            height: 78,
        },
        textract: {
            name: "Textract",
            icon: "textract",
            fillColor: "#01A88D",
            width: 78,
            height: 78,
        },
        forecast: {
            name: "Forecast",
            icon: "forecast",
            fillColor: "#01A88D",
            width: 78,
            height: 78,
        },
        personalize: {
            name: "Personalize",
            icon: "personalize",
            fillColor: "#01A88D",
            width: 78,
            height: 78,
        },
        kendra: {
            name: "Kendra",
            icon: "kendra",
            fillColor: "#01A88D",
            width: 78,
            height: 78,
        },
        codeWhisperer: {
            name: "CodeWhisperer",
            icon: "codewhisperer",
            fillColor: "#01A88D",
            width: 78,
            height: 78,
        },
        bedrock: {
            name: "Bedrock",
            icon: "bedrock",
            fillColor: "#01A88D",
            width: 78,
            height: 78,
        },
        q: {
            name: "Amazon Q",
            icon: "q",
            fillColor: "#01A88D",
            width: 78,
            height: 78,
        },
    },
    // ============================================================================
    // IOT
    // ============================================================================
    iot: {
        iotCore: {
            name: "IoT Core",
            icon: "iot_core",
            fillColor: "#7AA116",
            width: 78,
            height: 78,
        },
        iotGreengrass: {
            name: "IoT Greengrass",
            icon: "iot_greengrass",
            fillColor: "#7AA116",
            width: 78,
            height: 78,
        },
        iotAnalytics: {
            name: "IoT Analytics",
            icon: "iot_analytics",
            fillColor: "#7AA116",
            width: 78,
            height: 78,
        },
        iotEvents: {
            name: "IoT Events",
            icon: "iot_events",
            fillColor: "#7AA116",
            width: 78,
            height: 78,
        },
        iotSiteWise: {
            name: "IoT SiteWise",
            icon: "iot_sitewise",
            fillColor: "#7AA116",
            width: 78,
            height: 78,
        },
        iotThingsGraph: {
            name: "IoT Things Graph",
            icon: "iot_things_graph",
            fillColor: "#7AA116",
            width: 78,
            height: 78,
        },
        iotDeviceDefender: {
            name: "IoT Device Defender",
            icon: "iot_device_defender",
            fillColor: "#7AA116",
            width: 78,
            height: 78,
        },
        iotDeviceManagement: {
            name: "IoT Device Management",
            icon: "iot_device_management",
            fillColor: "#7AA116",
            width: 78,
            height: 78,
        },
        iotButton: {
            name: "IoT Button",
            icon: "iot_button",
            fillColor: "#7AA116",
            width: 78,
            height: 78,
        },
    },
    // ============================================================================
    // CONTAINERS
    // ============================================================================
    containers: {
        ecr: {
            name: "ECR",
            icon: "ecr",
            fillColor: "#ED7100",
            width: 78,
            height: 78,
        },
        ecrImage: {
            name: "ECR Image",
            icon: "ecr_image",
            fillColor: "#ED7100",
            width: 78,
            height: 78,
        },
        ecrRegistry: {
            name: "ECR Registry",
            icon: "ecr_registry",
            fillColor: "#ED7100",
            width: 78,
            height: 78,
        },
        ecsService: {
            name: "ECS Service",
            icon: "ecs_service",
            fillColor: "#ED7100",
            width: 78,
            height: 78,
        },
        ecsTask: {
            name: "ECS Task",
            icon: "ecs_task",
            fillColor: "#ED7100",
            width: 78,
            height: 78,
        },
        ecsContainer: {
            name: "ECS Container",
            icon: "container",
            fillColor: "#ED7100",
            width: 78,
            height: 78,
        },
        eksCloud: {
            name: "EKS Cloud",
            icon: "eks_cloud",
            fillColor: "#ED7100",
            width: 78,
            height: 78,
        },
    },
    // ============================================================================
    // GENERAL / RESOURCES
    // ============================================================================
    general: {
        user: {
            name: "User",
            icon: "user",
            fillColor: "#232F3D",
            width: 78,
            height: 78,
        },
        users: {
            name: "Users",
            icon: "users",
            fillColor: "#232F3D",
            width: 78,
            height: 78,
        },
        client: {
            name: "Client",
            icon: "client",
            fillColor: "#232F3D",
            width: 78,
            height: 78,
        },
        mobileClient: {
            name: "Mobile Client",
            icon: "mobile_client",
            fillColor: "#232F3D",
            width: 41,
            height: 78,
        },
        traditionalServer: {
            name: "Traditional Server",
            icon: "traditional_server",
            fillColor: "#232F3D",
            width: 45,
            height: 78,
        },
        corporateDataCenter: {
            name: "Data Center",
            icon: "corporate_data_center",
            fillColor: "#232F3D",
            width: 53,
            height: 78,
        },
        officeBuilding: {
            name: "Office Building",
            icon: "office_building",
            fillColor: "#232F3D",
            width: 50,
            height: 78,
        },
        internet: {
            name: "Internet",
            icon: "internet",
            fillColor: "#232F3D",
            width: 78,
            height: 48,
        },
        globe: {
            name: "Globe",
            icon: "globe",
            fillColor: "#232F3D",
            width: 78,
            height: 78,
        },
        genericDatabase: {
            name: "Generic Database",
            icon: "generic_database",
            fillColor: "#232F3D",
            width: 59,
            height: 78,
        },
        genericApplication: {
            name: "Generic Application",
            icon: "generic_application",
            fillColor: "#232F3D",
            width: 78,
            height: 78,
        },
        genericFirewall: {
            name: "Generic Firewall",
            icon: "generic_firewall",
            fillColor: "#232F3D",
            width: 78,
            height: 66,
        },
        disk: {
            name: "Disk",
            icon: "disk",
            fillColor: "#232F3D",
            width: 78,
            height: 78,
        },
        document: {
            name: "Document",
            icon: "document",
            fillColor: "#232F3D",
            width: 57,
            height: 78,
        },
        documents: {
            name: "Documents",
            icon: "documents",
            fillColor: "#232F3D",
            width: 64,
            height: 78,
        },
        folder: {
            name: "Folder",
            icon: "folder",
            fillColor: "#232F3D",
            width: 78,
            height: 71,
        },
        gear: {
            name: "Gear",
            icon: "gear",
            fillColor: "#232F3D",
            width: 78,
            height: 78,
        },
        servers: {
            name: "Servers",
            icon: "servers",
            fillColor: "#232F3D",
            width: 78,
            height: 78,
        },
    },
};
// ============================================================================
// GROUPS
// ============================================================================
/**
 * AWS4 group/container style definitions.
 * Used for creating VPC, Region, Subnet, and other container shapes.
 */
const AWS4_GROUPS = {
    awsCloud: {
        name: "AWS Cloud",
        grIcon: "group_aws_cloud_alt",
        strokeColor: "#232F3E",
        fillColor: "none",
        fontColor: "#232F3E",
        dashed: false,
    },
    awsCloudAlt: {
        name: "AWS Cloud (Alt)",
        grIcon: "group_aws_cloud",
        strokeColor: "#232F3E",
        fillColor: "none",
        fontColor: "#232F3E",
        dashed: false,
    },
    region: {
        name: "Region",
        grIcon: "group_region",
        strokeColor: "#00A4A6",
        fillColor: "none",
        fontColor: "#147EBA",
        dashed: true,
    },
    availabilityZone: {
        name: "Availability Zone",
        strokeColor: "#147EBA",
        fillColor: "none",
        fontColor: "#147EBA",
        dashed: true,
        simple: true, // No grIcon, uses simple rectangle
    },
    securityGroup: {
        name: "Security Group",
        strokeColor: "#DD3522",
        fillColor: "none",
        fontColor: "#DD3522",
        dashed: false,
        simple: true,
    },
    vpc: {
        name: "VPC",
        grIcon: "group_vpc2",
        strokeColor: "#8C4FFF",
        fillColor: "none",
        fontColor: "#AAB7B8",
        dashed: false,
    },
    privateSubnet: {
        name: "Private Subnet",
        grIcon: "group_security_group",
        strokeColor: "#00A4A6",
        fillColor: "#E6F6F7",
        fontColor: "#147EBA",
        dashed: false,
        grStroke: 0,
    },
    publicSubnet: {
        name: "Public Subnet",
        grIcon: "group_security_group",
        strokeColor: "#7AA116",
        fillColor: "#F2F6E8",
        fontColor: "#248814",
        dashed: false,
        grStroke: 0,
    },
    autoScalingGroup: {
        name: "Auto Scaling Group",
        grIcon: "group_auto_scaling_group",
        strokeColor: "#D86613",
        fillColor: "none",
        fontColor: "#D86613",
        dashed: true,
        centered: true,
    },
    ec2InstanceContents: {
        name: "EC2 Instance Contents",
        grIcon: "group_ec2_instance_contents",
        strokeColor: "#D86613",
        fillColor: "none",
        fontColor: "#D86613",
        dashed: false,
    },
    elasticBeanstalkContainer: {
        name: "Elastic Beanstalk Container",
        grIcon: "group_elastic_beanstalk",
        strokeColor: "#D86613",
        fillColor: "none",
        fontColor: "#D86613",
        dashed: false,
    },
    spotFleet: {
        name: "Spot Fleet",
        grIcon: "group_spot_fleet",
        strokeColor: "#D86613",
        fillColor: "none",
        fontColor: "#D86613",
        dashed: false,
    },
    stepFunctionsWorkflow: {
        name: "Step Functions Workflow",
        grIcon: "group_aws_step_functions_workflow",
        strokeColor: "#CD2264",
        fillColor: "none",
        fontColor: "#CD2264",
        dashed: false,
    },
    awsAccount: {
        name: "AWS Account",
        grIcon: "group_account",
        strokeColor: "#CD2264",
        fillColor: "none",
        fontColor: "#CD2264",
        dashed: false,
    },
    corporateDataCenter: {
        name: "Corporate Data Center",
        grIcon: "group_corporate_data_center",
        strokeColor: "#7D8998",
        fillColor: "none",
        fontColor: "#5A6C86",
        dashed: false,
    },
    serverContents: {
        name: "Server Contents",
        grIcon: "group_on_premise",
        strokeColor: "#7D8998",
        fillColor: "none",
        fontColor: "#5A6C86",
        dashed: false,
    },
    iotGreengrassDeployment: {
        name: "IoT Greengrass Deployment",
        grIcon: "group_iot_greengrass_deployment",
        strokeColor: "#7AA116",
        fillColor: "none",
        fontColor: "#3F8624",
        dashed: false,
    },
    iotGreengrass: {
        name: "IoT Greengrass",
        grIcon: "group_iot_greengrass",
        strokeColor: "#7AA116",
        fillColor: "none",
        fontColor: "#3F8624",
        dashed: false,
    },
    generic: {
        name: "Generic Group",
        strokeColor: "#5A6C86",
        fillColor: "none",
        fontColor: "#5A6C86",
        dashed: true,
        simple: true,
    },
    genericFilled: {
        name: "Generic Group (Filled)",
        strokeColor: "none",
        fillColor: "#EFF0F3",
        fontColor: "#232F3D",
        dashed: false,
        simple: true,
    },
};
// ============================================================================
// STYLE BUILDER FUNCTIONS
// ============================================================================
/**
 * Build a complete style string for an AWS4 resource icon.
 * @param iconName - Icon identifier (e.g., 'lambda', 'ec2', 's3')
 * @param options - Style options
 * @returns Complete style string for insertVertex
 */
function buildResourceIconStyle(iconName, options = {}) {
    const fillColor = options.fillColor || "#232F3E";
    return (AWS4_BASE.RESOURCE_ICON +
        `resourceIcon;resIcon=mxgraph.aws4.${iconName};fillColor=${fillColor}`);
}
/**
 * Build a complete style string for an AWS4 product icon.
 * @param iconName - Icon identifier
 * @param options - Style options
 * @returns Complete style string for insertVertex
 */
function buildProductIconStyle(iconName, options = {}) {
    const fillColor = options.fillColor || "#232F3D";
    return AWS4_BASE.PRODUCT_ICON + `${iconName};fillColor=${fillColor}`;
}
/**
 * Build a complete style string for an AWS4 group container.
 * @param groupType - Group type from AWS4_GROUPS (e.g., 'vpc', 'region')
 * @param options - Style options
 * @returns Complete style string for insertVertex
 */
function buildGroupStyle(groupType, options = {}) {
    const groupDef = AWS4_GROUPS[groupType] || AWS4_GROUPS.generic;
    const strokeColor = options.strokeColor || groupDef.strokeColor;
    const fillColor = options.fillColor || groupDef.fillColor;
    const fontColor = options.fontColor || groupDef.fontColor;
    const dashed = groupDef.dashed ? ";dashed=1" : "";
    // Simple groups without grIcon
    if (groupDef.simple) {
        return (`fillColor=${fillColor};strokeColor=${strokeColor}${dashed};` +
            `verticalAlign=top;fontStyle=0;fontColor=${fontColor};whiteSpace=wrap;html=1;`);
    }
    // Groups with grIcon
    const grStroke = groupDef.grStroke !== undefined ? `;grStroke=${groupDef.grStroke}` : "";
    const align = groupDef.centered
        ? "align=center;spacingTop=25;"
        : "align=left;spacingLeft=30;";
    return (AWS4_BASE.GROUP +
        `group;grIcon=mxgraph.aws4.${groupDef.grIcon}${grStroke};` +
        `strokeColor=${strokeColor};fillColor=${fillColor}${dashed};` +
        `verticalAlign=top;${align}fontColor=${fontColor}`);
}
/**
 * Look up an icon definition by name across all categories.
 * @param iconName - Icon name to find (case-insensitive)
 * @param category - Optional category hint for faster lookup
 * @returns Icon definition or null if not found
 */
function findIcon(iconName, category) {
    const lowerName = iconName.toLowerCase();
    // If category provided, search there first
    if (category && AWS4_ICONS[category]) {
        const icon = Object.entries(AWS4_ICONS[category]).find(([key, def]) => key.toLowerCase() === lowerName ||
            def.icon.toLowerCase() === lowerName ||
            def.name.toLowerCase() === lowerName);
        if (icon)
            return { key: icon[0], ...icon[1], category };
    }
    // Search all categories
    for (const [cat, icons] of Object.entries(AWS4_ICONS)) {
        const icon = Object.entries(icons).find(([key, def]) => key.toLowerCase() === lowerName ||
            def.icon.toLowerCase() === lowerName ||
            def.name.toLowerCase() === lowerName);
        if (icon)
            return { key: icon[0], ...icon[1], category: cat };
    }
    return null;
}
/**
 * Get all available icon categories.
 * @returns Array of category names
 */
function getCategories() {
    return Object.keys(AWS4_ICONS);
}
/**
 * Get all icons in a specific category.
 * @param category - Category name
 * @returns Object with icon definitions or null if category not found
 */
function getIconsByCategory(category) {
    return AWS4_ICONS[category] || null;
}
/**
 * Get all available group types.
 * @returns Array of group type names
 */
function getGroupTypes() {
    return Object.keys(AWS4_GROUPS);
}
/**
 * Parse a style string into an object.
 * @param styleString - mxGraph style string
 * @returns Style object with key-value pairs
 */
function parseStyleString(styleString) {
    if (!styleString)
        return {};
    const result = {};
    const pairs = styleString.split(";");
    for (const pair of pairs) {
        if (pair) {
            const [key, value] = pair.split("=");
            if (key) {
                result[key] = value;
            }
        }
    }
    return result;
}
/**
 * Convert a style object to a style string.
 * @param styleObj - Style object
 * @returns mxGraph style string
 */
function buildStyleString(styleObj) {
    if (!styleObj)
        return "";
    const parts = [];
    for (const key in styleObj) {
        if (Object.prototype.hasOwnProperty.call(styleObj, key)) {
            parts.push(`${key}=${styleObj[key]}`);
        }
    }
    return parts.join(";");
}

// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0
class CellManager {
    constructor(api) {
        this._api = api;
    }
    _buildStyleString(styleObj) {
        if (!styleObj)
            return "";
        const parts = [];
        for (const key in styleObj) {
            if (Object.prototype.hasOwnProperty.call(styleObj, key)) {
                const value = styleObj[key];
                if (value !== undefined) {
                    parts.push(`${key}=${value}`);
                }
            }
        }
        return parts.join(";");
    }
    _parseStyleString(styleString) {
        if (!styleString)
            return {};
        const result = {};
        const pairs = styleString.split(";");
        for (const pair of pairs) {
            if (pair) {
                const [key, value] = pair.split("=");
                if (key) {
                    result[key] = value;
                }
            }
        }
        return result;
    }
    insertVertex(options) {
        try {
            const graph = this._api.graph;
            const model = this._api.model;
            if (!graph || !model) {
                return { success: false, error: "API not initialized" };
            }
            if (!options || !options.geometry) {
                return { success: false, error: "Geometry is required" };
            }
            const geo = options.geometry;
            const parent = options.parentId
                ? model.getCell(options.parentId)
                : graph.getDefaultParent();
            if (!parent) {
                return { success: false, error: "Parent cell not found" };
            }
            const id = options.id || null;
            const label = options.label || "";
            const style = typeof options.style === "string"
                ? options.style
                : this._buildStyleString(options.style);
            model.beginUpdate();
            try {
                const cell = graph.insertVertex(parent, id, label, geo.x, geo.y, geo.width, geo.height, style);
                return { success: true, data: { id: cell.getId() } };
            }
            finally {
                model.endUpdate();
            }
        }
        catch (e) {
            return { success: false, error: e.message };
        }
    }
    insertEdge(options) {
        try {
            const graph = this._api.graph;
            const model = this._api.model;
            if (!graph || !model) {
                return { success: false, error: "API not initialized" };
            }
            if (!options || !options.sourceId || !options.targetId) {
                return { success: false, error: "Source and target IDs are required" };
            }
            const source = model.getCell(options.sourceId);
            const target = model.getCell(options.targetId);
            if (!source) {
                return { success: false, error: "Source cell not found" };
            }
            if (!target) {
                return { success: false, error: "Target cell not found" };
            }
            const parent = graph.getDefaultParent();
            const id = options.id || null;
            const label = options.label || "";
            const style = typeof options.style === "string"
                ? options.style
                : this._buildStyleString(options.style);
            model.beginUpdate();
            try {
                const cell = graph.insertEdge(parent, id, label, source, target, style);
                if (options.waypoints && options.waypoints.length > 0) {
                    const geometry = cell.getGeometry();
                    if (geometry) {
                        geometry.points = options.waypoints.map((wp) => new mxPoint(wp.x, wp.y));
                    }
                }
                return { success: true, data: { id: cell.getId() } };
            }
            finally {
                model.endUpdate();
            }
        }
        catch (e) {
            return { success: false, error: e.message };
        }
    }
    removeCell(cellId) {
        try {
            const graph = this._api.graph;
            const model = this._api.model;
            if (!graph || !model) {
                return { success: false, error: "API not initialized" };
            }
            const cell = model.getCell(cellId);
            if (!cell) {
                return { success: false, error: "Cell not found" };
            }
            model.beginUpdate();
            try {
                graph.removeCells([cell]);
            }
            finally {
                model.endUpdate();
            }
            return { success: true };
        }
        catch (e) {
            return { success: false, error: e.message };
        }
    }
    removeCells(cellIds) {
        try {
            const graph = this._api.graph;
            const model = this._api.model;
            if (!graph || !model) {
                return { success: false, error: "API not initialized" };
            }
            if (!Array.isArray(cellIds)) {
                return { success: false, error: "cellIds must be an array" };
            }
            const cells = cellIds
                .map((id) => model.getCell(id))
                .filter((cell) => cell !== null);
            if (cells.length === 0) {
                return { success: false, error: "No valid cells found" };
            }
            model.beginUpdate();
            try {
                graph.removeCells(cells);
            }
            finally {
                model.endUpdate();
            }
            return { success: true, data: { removed: cells.length } };
        }
        catch (e) {
            return { success: false, error: e.message };
        }
    }
    getCell(cellId) {
        try {
            const model = this._api.model;
            if (!model) {
                return { success: false, error: "API not initialized" };
            }
            const cell = model.getCell(cellId);
            if (!cell) {
                return { success: false, error: "Cell not found" };
            }
            const cellData = this._cellToData(cell, model);
            return { success: true, data: cellData };
        }
        catch (e) {
            return { success: false, error: e.message };
        }
    }
    _cellToData(cell, model) {
        const geo = cell.getGeometry();
        const data = {
            id: cell.getId(),
            label: cell.getValue() || "",
            style: cell.getStyle() || "",
            isVertex: model.isVertex(cell),
            isEdge: model.isEdge(cell),
            parentId: cell.getParent() ? cell.getParent().getId() : null,
        };
        if (geo && data.isVertex) {
            data.geometry = {
                x: geo.x,
                y: geo.y,
                width: geo.width,
                height: geo.height,
            };
        }
        if (data.isEdge) {
            data.sourceId = cell.source ? cell.source.getId() : null;
            data.targetId = cell.target ? cell.target.getId() : null;
        }
        return data;
    }
    getCells() {
        try {
            const graph = this._api.graph;
            const model = this._api.model;
            if (!graph || !model) {
                return { success: false, error: "API not initialized" };
            }
            const parent = graph.getDefaultParent();
            const children = model.getChildren(parent) || [];
            const cellsData = children.map((cell) => this._cellToData(cell, model));
            return { success: true, data: cellsData };
        }
        catch (e) {
            return { success: false, error: e.message };
        }
    }
    getVertices() {
        try {
            const graph = this._api.graph;
            const model = this._api.model;
            if (!graph || !model) {
                return { success: false, error: "API not initialized" };
            }
            const parent = graph.getDefaultParent();
            const children = model.getChildren(parent) || [];
            const vertices = children
                .filter((cell) => model.isVertex(cell))
                .map((cell) => this._cellToData(cell, model));
            return { success: true, data: vertices };
        }
        catch (e) {
            return { success: false, error: e.message };
        }
    }
    getEdges() {
        try {
            const graph = this._api.graph;
            const model = this._api.model;
            if (!graph || !model) {
                return { success: false, error: "API not initialized" };
            }
            const parent = graph.getDefaultParent();
            const children = model.getChildren(parent) || [];
            const edges = children
                .filter((cell) => model.isEdge(cell))
                .map((cell) => this._cellToData(cell, model));
            return { success: true, data: edges };
        }
        catch (e) {
            return { success: false, error: e.message };
        }
    }
    updateCell(cellId, updates) {
        try {
            const graph = this._api.graph;
            const model = this._api.model;
            if (!graph || !model) {
                return { success: false, error: "API not initialized" };
            }
            const cell = model.getCell(cellId);
            if (!cell) {
                return { success: false, error: "Cell not found" };
            }
            model.beginUpdate();
            try {
                if (updates.label !== undefined) {
                    model.setValue(cell, updates.label);
                }
                if (updates.geometry) {
                    const geo = cell.getGeometry();
                    if (geo) {
                        const newGeo = geo.clone();
                        if (updates.geometry.x !== undefined)
                            newGeo.x = updates.geometry.x;
                        if (updates.geometry.y !== undefined)
                            newGeo.y = updates.geometry.y;
                        if (updates.geometry.width !== undefined)
                            newGeo.width = updates.geometry.width;
                        if (updates.geometry.height !== undefined)
                            newGeo.height = updates.geometry.height;
                        model.setGeometry(cell, newGeo);
                    }
                }
                if (updates.style) {
                    let styleString;
                    if (typeof updates.style === "string") {
                        styleString = updates.style;
                    }
                    else {
                        const currentStyle = this._parseStyleString(cell.getStyle());
                        const mergedStyle = { ...currentStyle, ...updates.style };
                        styleString = this._buildStyleString(mergedStyle);
                    }
                    model.setStyle(cell, styleString);
                }
            }
            finally {
                model.endUpdate();
            }
            return { success: true };
        }
        catch (e) {
            return { success: false, error: e.message };
        }
    }
    moveCell(cellId, x, y) {
        return this.updateCell(cellId, { geometry: { x, y } });
    }
    resizeCell(cellId, width, height) {
        return this.updateCell(cellId, { geometry: { width, height } });
    }
    cloneCell(cellId, offsetX = 20, offsetY = 20) {
        try {
            const graph = this._api.graph;
            const model = this._api.model;
            if (!graph || !model) {
                return { success: false, error: "API not initialized" };
            }
            const cell = model.getCell(cellId);
            if (!cell) {
                return { success: false, error: "Cell not found" };
            }
            model.beginUpdate();
            try {
                const clones = graph.cloneCells([cell]);
                if (clones && clones.length > 0) {
                    const clone = clones[0];
                    const geo = clone.getGeometry();
                    if (geo) {
                        geo.x += offsetX;
                        geo.y += offsetY;
                    }
                    graph.addCells([clone], graph.getDefaultParent());
                    return { success: true, data: { id: clone.getId() } };
                }
                return { success: false, error: "Clone failed" };
            }
            finally {
                model.endUpdate();
            }
        }
        catch (e) {
            return { success: false, error: e.message };
        }
    }
    groupCells(cellIds) {
        try {
            const graph = this._api.graph;
            const model = this._api.model;
            if (!graph || !model) {
                return { success: false, error: "API not initialized" };
            }
            if (!Array.isArray(cellIds) || cellIds.length < 2) {
                return {
                    success: false,
                    error: "At least 2 cells required for grouping",
                };
            }
            const cells = cellIds
                .map((id) => model.getCell(id))
                .filter((cell) => cell !== null);
            if (cells.length < 2) {
                return { success: false, error: "At least 2 valid cells required" };
            }
            model.beginUpdate();
            try {
                const group = graph.groupCells(null, 0, cells);
                return { success: true, data: { id: group.getId() } };
            }
            finally {
                model.endUpdate();
            }
        }
        catch (e) {
            return { success: false, error: e.message };
        }
    }
    ungroupCells(groupId) {
        try {
            const graph = this._api.graph;
            const model = this._api.model;
            if (!graph || !model) {
                return { success: false, error: "API not initialized" };
            }
            const group = model.getCell(groupId);
            if (!group) {
                return { success: false, error: "Group not found" };
            }
            model.beginUpdate();
            try {
                const cells = graph.ungroupCells([group]);
                const releasedIds = cells.map((cell) => cell.getId());
                return { success: true, data: { ids: releasedIds } };
            }
            finally {
                model.endUpdate();
            }
        }
        catch (e) {
            return { success: false, error: e.message };
        }
    }
    getParent(cellId) {
        try {
            const model = this._api.model;
            if (!model) {
                return { success: false, error: "API not initialized" };
            }
            const cell = model.getCell(cellId);
            if (!cell) {
                return { success: false, error: "Cell not found" };
            }
            const parent = cell.getParent();
            if (!parent || parent === model.getRoot()) {
                return { success: true, data: null };
            }
            return { success: true, data: this._cellToData(parent, model) };
        }
        catch (e) {
            return { success: false, error: e.message };
        }
    }
    getChildren(cellId) {
        try {
            const model = this._api.model;
            if (!model) {
                return { success: false, error: "API not initialized" };
            }
            const cell = model.getCell(cellId);
            if (!cell) {
                return { success: false, error: "Cell not found" };
            }
            const children = model.getChildren(cell) || [];
            const childrenData = children.map((child) => this._cellToData(child, model));
            return { success: true, data: childrenData };
        }
        catch (e) {
            return { success: false, error: e.message };
        }
    }
    getConnectedEdges(cellId, incoming = true, outgoing = true) {
        try {
            const graph = this._api.graph;
            const model = this._api.model;
            if (!graph || !model) {
                return { success: false, error: "API not initialized" };
            }
            const cell = model.getCell(cellId);
            if (!cell) {
                return { success: false, error: "Cell not found" };
            }
            const edges = graph.getEdges(cell, null, incoming, outgoing) || [];
            const edgesData = edges.map((edge) => this._cellToData(edge, model));
            return { success: true, data: edgesData };
        }
        catch (e) {
            return { success: false, error: e.message };
        }
    }
    getSelection() {
        try {
            const graph = this._api.graph;
            const model = this._api.model;
            if (!graph || !model) {
                return { success: false, error: "API not initialized" };
            }
            const cells = graph.getSelectionCells() || [];
            const cellsData = cells.map((cell) => this._cellToData(cell, model));
            return { success: true, data: cellsData };
        }
        catch (e) {
            return { success: false, error: e.message };
        }
    }
    setSelection(cellIds) {
        try {
            const graph = this._api.graph;
            const model = this._api.model;
            if (!graph || !model) {
                return { success: false, error: "API not initialized" };
            }
            const cells = cellIds
                .map((id) => model.getCell(id))
                .filter((cell) => cell !== null);
            graph.setSelectionCells(cells);
            return { success: true };
        }
        catch (e) {
            return { success: false, error: e.message };
        }
    }
    clearSelection() {
        try {
            const graph = this._api.graph;
            if (!graph) {
                return { success: false, error: "API not initialized" };
            }
            graph.clearSelection();
            return { success: true };
        }
        catch (e) {
            return { success: false, error: e.message };
        }
    }
    // ===========================================================================
    // AWS4 ICON METHODS
    // ===========================================================================
    insertAwsIcon(options) {
        try {
            if (!options) {
                return { success: false, error: "Options are required" };
            }
            if (options.style) {
                const geometry = {
                    x: options.geometry?.x || 0,
                    y: options.geometry?.y || 0,
                    width: options.geometry?.width || 78,
                    height: options.geometry?.height || 78,
                };
                return this.insertVertex({
                    id: options.id,
                    parentId: options.parentId,
                    label: options.label || "",
                    geometry,
                    style: this._parseStyleString(options.style),
                });
            }
            if (!options.icon) {
                return { success: false, error: "Icon name or style is required" };
            }
            const iconDef = findIcon(options.icon, options.category);
            const fillColor = options.fillColor || (iconDef ? iconDef.fillColor : "#232F3E");
            const iconName = iconDef ? iconDef.icon : options.icon;
            const style = buildResourceIconStyle(iconName, { fillColor });
            const geometry = {
                x: options.geometry?.x || 0,
                y: options.geometry?.y || 0,
                width: options.geometry?.width || iconDef?.width || 78,
                height: options.geometry?.height || iconDef?.height || 78,
            };
            return this.insertVertex({
                id: options.id,
                parentId: options.parentId,
                label: options.label || iconDef?.name || options.icon,
                geometry,
                style: this._parseStyleString(style),
            });
        }
        catch (e) {
            return { success: false, error: e.message };
        }
    }
    insertAwsGroup(options) {
        try {
            if (!options) {
                return { success: false, error: "Options are required" };
            }
            if (!options.geometry ||
                options.geometry.width === undefined ||
                options.geometry.height === undefined) {
                return {
                    success: false,
                    error: "Geometry with width and height is required for groups",
                };
            }
            if (options.style) {
                return this.insertVertex({
                    id: options.id,
                    parentId: options.parentId,
                    label: options.label || "",
                    geometry: options.geometry,
                    style: this._parseStyleString(options.style),
                });
            }
            if (!options.groupType) {
                return { success: false, error: "Group type or style is required" };
            }
            if (!AWS4_GROUPS[options.groupType]) {
                return {
                    success: false,
                    error: `Unknown group type: ${options.groupType}. Valid types: ${Object.keys(AWS4_GROUPS).join(", ")}`,
                };
            }
            const style = buildGroupStyle(options.groupType, {
                strokeColor: options.strokeColor,
                fillColor: options.fillColor,
                fontColor: options.fontColor,
            });
            const groupDef = AWS4_GROUPS[options.groupType];
            const label = options.label !== undefined ? options.label : groupDef.name;
            return this.insertVertex({
                id: options.id,
                parentId: options.parentId,
                label,
                geometry: options.geometry,
                style: this._parseStyleString(style),
            });
        }
        catch (e) {
            return { success: false, error: e.message };
        }
    }
    getAwsGroupTypes() {
        try {
            const types = Object.entries(AWS4_GROUPS).map(([key, def]) => ({
                type: key,
                name: def.name,
                hasIcon: !def.simple,
            }));
            return { success: true, data: types };
        }
        catch (e) {
            return { success: false, error: e.message };
        }
    }
    /**
     * Create a data URI from an SVG string.
     * @param svgContent - SVG content as string
     * @returns URL-encoded data URI
     */
    createSvgDataUri(svgContent) {
        // URL encode the SVG for draw.io compatibility
        const encoded = encodeURIComponent(svgContent)
            .replace(/'/g, "%27")
            .replace(/"/g, "%22");
        return `data:image/svg+xml,${encoded}`;
    }
    /**
     * Create a data URI from a PNG/JPG image buffer or base64 string.
     * @param imageData - Image data as Buffer or base64 string
     * @param mimeType - MIME type (default: 'image/png')
     * @returns Base64-encoded data URI
     */
    createImageDataUri(imageData, mimeType = "image/png") {
        const base64 = typeof imageData === "string" ? imageData : imageData.toString("base64");
        return `data:${mimeType},${base64};base64,${base64}`;
    }
    /**
     * Insert a vertex with a custom image (SVG or raster).
     * @param options - Image vertex options
     * @returns API result with cell ID
     */
    insertImageVertex(options) {
        const baseStyle = {
            shape: "image",
            verticalLabelPosition: "bottom",
            labelBackgroundColor: "default",
            verticalAlign: "top",
            aspect: "fixed",
            imageAspect: options.maintainAspect !== false ? "0" : undefined,
            image: options.imageDataUri,
            ...options.styleOverrides,
        };
        return this.insertVertex({
            id: options.id,
            label: options.label,
            geometry: {
                x: options.geometry.x,
                y: options.geometry.y,
                width: options.geometry.width || 100,
                height: options.geometry.height || 100,
            },
            style: baseStyle,
        });
    }
}

// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0
const STYLE_MAP = {
    fillColor: "fillColor",
    strokeColor: "strokeColor",
    strokeWidth: "strokeWidth",
    fontColor: "fontColor",
    fontSize: "fontSize",
    fontFamily: "fontFamily",
    opacity: "opacity",
    rounded: "rounded",
    shadow: "shadow",
    shape: "shape",
    perimeter: "perimeter",
    verticalAlign: "verticalAlign",
    align: "align",
    spacingTop: "spacingTop",
    spacingBottom: "spacingBottom",
    spacingLeft: "spacingLeft",
    spacingRight: "spacingRight",
    dashed: "dashed",
    dashPattern: "dashPattern",
    gradientColor: "gradientColor",
    gradientDirection: "gradientDirection",
    glass: "glass",
    labelBackgroundColor: "labelBackgroundColor",
    labelBorderColor: "labelBorderColor",
};
class StyleManager {
    constructor(api) {
        this._api = api;
    }
    _buildStyleString(styleObj) {
        if (!styleObj)
            return "";
        const parts = [];
        for (const key in styleObj) {
            if (Object.prototype.hasOwnProperty.call(styleObj, key)) {
                const mxKey = STYLE_MAP[key] || key;
                parts.push(`${mxKey}=${styleObj[key]}`);
            }
        }
        return parts.join(";");
    }
    _parseStyleString(styleString) {
        if (!styleString)
            return {};
        const result = {};
        const pairs = styleString.split(";");
        for (const pair of pairs) {
            if (pair) {
                const eqIndex = pair.indexOf("=");
                if (eqIndex > 0) {
                    const key = pair.substring(0, eqIndex);
                    const value = pair.substring(eqIndex + 1);
                    result[key] = value;
                }
                else if (pair.length > 0) {
                    result[pair] = "1";
                }
            }
        }
        return result;
    }
    getStyle(cellId) {
        try {
            const model = this._api.model;
            if (!model) {
                return { success: false, error: "API not initialized" };
            }
            const cell = model.getCell(cellId);
            if (!cell) {
                return { success: false, error: "Cell not found" };
            }
            const styleString = cell.getStyle() || "";
            const styleObj = this._parseStyleString(styleString);
            return { success: true, data: styleObj };
        }
        catch (e) {
            return { success: false, error: e.message };
        }
    }
    setStyle(cellId, style) {
        try {
            const model = this._api.model;
            if (!model) {
                return { success: false, error: "API not initialized" };
            }
            const cell = model.getCell(cellId);
            if (!cell) {
                return { success: false, error: "Cell not found" };
            }
            const styleString = this._buildStyleString(style);
            model.beginUpdate();
            try {
                model.setStyle(cell, styleString);
            }
            finally {
                model.endUpdate();
            }
            return { success: true };
        }
        catch (e) {
            return { success: false, error: e.message };
        }
    }
    updateStyle(cellId, updates) {
        try {
            const model = this._api.model;
            if (!model) {
                return { success: false, error: "API not initialized" };
            }
            const cell = model.getCell(cellId);
            if (!cell) {
                return { success: false, error: "Cell not found" };
            }
            const currentStyle = this._parseStyleString(cell.getStyle());
            const mergedStyle = {
                ...currentStyle,
            };
            for (const key in updates) {
                if (Object.prototype.hasOwnProperty.call(updates, key)) {
                    const mxKey = STYLE_MAP[key] || key;
                    mergedStyle[mxKey] = updates[key];
                }
            }
            const styleString = this._buildStyleString(mergedStyle);
            model.beginUpdate();
            try {
                model.setStyle(cell, styleString);
            }
            finally {
                model.endUpdate();
            }
            return { success: true };
        }
        catch (e) {
            return { success: false, error: e.message };
        }
    }
    getCellStyleString(cellId) {
        try {
            const model = this._api.model;
            if (!model) {
                return { success: false, error: "API not initialized" };
            }
            const cell = model.getCell(cellId);
            if (!cell) {
                return { success: false, error: "Cell not found" };
            }
            return { success: true, data: cell.getStyle() || "" };
        }
        catch (e) {
            return { success: false, error: e.message };
        }
    }
    setCellStyleString(cellId, styleString) {
        try {
            const model = this._api.model;
            if (!model) {
                return { success: false, error: "API not initialized" };
            }
            const cell = model.getCell(cellId);
            if (!cell) {
                return { success: false, error: "Cell not found" };
            }
            model.beginUpdate();
            try {
                model.setStyle(cell, styleString);
            }
            finally {
                model.endUpdate();
            }
            return { success: true };
        }
        catch (e) {
            return { success: false, error: e.message };
        }
    }
    applyStyleToSelection(style) {
        try {
            const graph = this._api.graph;
            const model = this._api.model;
            if (!graph || !model) {
                return { success: false, error: "API not initialized" };
            }
            const cells = graph.getSelectionCells() || [];
            if (cells.length === 0) {
                return { success: false, error: "No cells selected" };
            }
            model.beginUpdate();
            try {
                for (const cell of cells) {
                    const currentStyle = this._parseStyleString(cell.getStyle());
                    const mergedStyle = {
                        ...currentStyle,
                    };
                    for (const key in style) {
                        if (Object.prototype.hasOwnProperty.call(style, key)) {
                            const mxKey = STYLE_MAP[key] || key;
                            mergedStyle[mxKey] = style[key];
                        }
                    }
                    const styleString = this._buildStyleString(mergedStyle);
                    model.setStyle(cell, styleString);
                }
            }
            finally {
                model.endUpdate();
            }
            return { success: true, data: { updated: cells.length } };
        }
        catch (e) {
            return { success: false, error: e.message };
        }
    }
    getDefaultVertexStyle() {
        try {
            const graph = this._api.graph;
            if (!graph) {
                return { success: false, error: "API not initialized" };
            }
            const stylesheet = graph.getStylesheet();
            const defaultStyle = stylesheet.getDefaultVertexStyle();
            const styleObj = {};
            if (defaultStyle) {
                if (defaultStyle instanceof Map) {
                    defaultStyle.forEach((value, key) => {
                        styleObj[key] = value;
                    });
                }
                else {
                    Object.assign(styleObj, defaultStyle);
                }
            }
            return { success: true, data: styleObj };
        }
        catch (e) {
            return { success: false, error: e.message };
        }
    }
    getDefaultEdgeStyle() {
        try {
            const graph = this._api.graph;
            if (!graph) {
                return { success: false, error: "API not initialized" };
            }
            const stylesheet = graph.getStylesheet();
            const defaultStyle = stylesheet.getDefaultEdgeStyle();
            const styleObj = {};
            if (defaultStyle) {
                if (defaultStyle instanceof Map) {
                    defaultStyle.forEach((value, key) => {
                        styleObj[key] = value;
                    });
                }
                else {
                    Object.assign(styleObj, defaultStyle);
                }
            }
            return { success: true, data: styleObj };
        }
        catch (e) {
            return { success: false, error: e.message };
        }
    }
    setDefaultVertexStyle(style) {
        try {
            const graph = this._api.graph;
            if (!graph) {
                return { success: false, error: "API not initialized" };
            }
            const stylesheet = graph.getStylesheet();
            const defaultStyle = stylesheet.getDefaultVertexStyle() || {};
            for (const key in style) {
                if (Object.prototype.hasOwnProperty.call(style, key)) {
                    const mxKey = STYLE_MAP[key] || key;
                    if (defaultStyle instanceof Map) {
                        defaultStyle.set(mxKey, style[key]);
                    }
                    else {
                        defaultStyle[mxKey] = style[key];
                    }
                }
            }
            return { success: true };
        }
        catch (e) {
            return { success: false, error: e.message };
        }
    }
    setDefaultEdgeStyle(style) {
        try {
            const graph = this._api.graph;
            if (!graph) {
                return { success: false, error: "API not initialized" };
            }
            const stylesheet = graph.getStylesheet();
            const defaultStyle = stylesheet.getDefaultEdgeStyle() || {};
            for (const key in style) {
                if (Object.prototype.hasOwnProperty.call(style, key)) {
                    const mxKey = STYLE_MAP[key] || key;
                    if (defaultStyle instanceof Map) {
                        defaultStyle.set(mxKey, style[key]);
                    }
                    else {
                        defaultStyle[mxKey] = style[key];
                    }
                }
            }
            return { success: true };
        }
        catch (e) {
            return { success: false, error: e.message };
        }
    }
    getComputedStyle(cellId) {
        try {
            const graph = this._api.graph;
            const model = this._api.model;
            if (!graph || !model) {
                return { success: false, error: "API not initialized" };
            }
            const cell = model.getCell(cellId);
            if (!cell) {
                return { success: false, error: "Cell not found" };
            }
            const state = graph.getView().getState(cell);
            if (!state || !state.style) {
                return this.getStyle(cellId);
            }
            const styleObj = {};
            if (state.style instanceof Map) {
                state.style.forEach((value, key) => {
                    styleObj[key] = value;
                });
            }
            else {
                Object.assign(styleObj, state.style);
            }
            return { success: true, data: styleObj };
        }
        catch (e) {
            return { success: false, error: e.message };
        }
    }
    removeStyleProperties(cellId, properties) {
        try {
            const model = this._api.model;
            if (!model) {
                return { success: false, error: "API not initialized" };
            }
            const cell = model.getCell(cellId);
            if (!cell) {
                return { success: false, error: "Cell not found" };
            }
            if (!Array.isArray(properties)) {
                return { success: false, error: "Properties must be an array" };
            }
            const currentStyle = this._parseStyleString(cell.getStyle());
            for (const prop of properties) {
                const mxKey = STYLE_MAP[prop] || prop;
                delete currentStyle[mxKey];
            }
            const styleString = this._buildStyleString(currentStyle);
            model.beginUpdate();
            try {
                model.setStyle(cell, styleString);
            }
            finally {
                model.endUpdate();
            }
            return { success: true };
        }
        catch (e) {
            return { success: false, error: e.message };
        }
    }
}

// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0
class IOManager {
    constructor(api) {
        this._api = api;
    }
    toXml() {
        try {
            const model = this._api.model;
            if (!model) {
                return { success: false, error: "API not initialized" };
            }
            const encoder = new mxCodec();
            const node = encoder.encode(model);
            const xml = mxUtils.getXml(node);
            return { success: true, data: xml };
        }
        catch (e) {
            return { success: false, error: e.message };
        }
    }
    fromXml(xml) {
        try {
            const model = this._api.model;
            if (!model) {
                return { success: false, error: "API not initialized" };
            }
            if (!xml || typeof xml !== "string") {
                return { success: false, error: "Invalid XML input" };
            }
            const doc = mxUtils.parseXml(xml);
            const parseError = doc.getElementsByTagName("parsererror");
            if (parseError.length > 0) {
                return { success: false, error: "XML parsing error" };
            }
            const codec = new mxCodec(doc);
            model.beginUpdate();
            try {
                codec.decode(doc.documentElement, model);
            }
            finally {
                model.endUpdate();
            }
            return { success: true };
        }
        catch (e) {
            return { success: false, error: e.message };
        }
    }
    exportSvg(options = {}) {
        try {
            const graph = this._api.graph;
            if (!graph) {
                return { success: false, error: "API not initialized" };
            }
            const border = options.border || 0;
            const background = options.background || null;
            if (typeof graph.getSvg === "function") {
                const svg = graph.getSvg(background, border);
                if (svg) {
                    const serializer = new XMLSerializer();
                    const svgString = serializer.serializeToString(svg);
                    return { success: true, data: svgString };
                }
            }
            const bounds = graph.getGraphBounds();
            if (!bounds) {
                return { success: false, error: "No content to export" };
            }
            const svgDoc = mxUtils.createXmlDocument();
            const root = svgDoc.createElementNS("http://www.w3.org/2000/svg", "svg");
            root.setAttribute("width", String(bounds.width + border * 2));
            root.setAttribute("height", String(bounds.height + border * 2));
            root.setAttribute("viewBox", `${bounds.x - border} ${bounds.y - border} ${bounds.width + border * 2} ${bounds.height + border * 2}`);
            svgDoc.appendChild(root);
            const serializer = new XMLSerializer();
            return { success: true, data: serializer.serializeToString(svgDoc) };
        }
        catch (e) {
            return { success: false, error: e.message };
        }
    }
    exportPng(options = {}) {
        try {
            const graph = this._api.graph;
            const ui = this._api.editorUi;
            if (!graph) {
                return { success: false, error: "API not initialized" };
            }
            const scale = options.scale || 1;
            const background = options.background || null;
            if (ui && typeof ui.getImageDataUri === "function") {
                const getImageDataUri = ui.getImageDataUri;
                return new Promise((resolve) => {
                    getImageDataUri(null, (dataUri) => {
                        if (dataUri) {
                            resolve({ success: true, data: dataUri });
                        }
                        else {
                            resolve({ success: false, error: "PNG export failed" });
                        }
                    }, background, scale);
                });
            }
            if (typeof graph.exportPng === "function") {
                const dataUrl = graph.exportPng(background, scale);
                if (dataUrl) {
                    return { success: true, data: dataUrl };
                }
            }
            return {
                success: false,
                error: "PNG export not available in this environment",
            };
        }
        catch (e) {
            return { success: false, error: e.message };
        }
    }
    importGraphML(xml) {
        try {
            const graph = this._api.graph;
            const model = this._api.model;
            if (!graph || !model) {
                return { success: false, error: "API not initialized" };
            }
            if (!xml || typeof xml !== "string") {
                return { success: false, error: "Invalid GraphML input" };
            }
            if (typeof mxGraphMlCodec !== "undefined" && mxGraphMlCodec) {
                const doc = mxUtils.parseXml(xml);
                const codec = new mxGraphMlCodec();
                model.beginUpdate();
                try {
                    codec.decode(doc, graph);
                }
                finally {
                    model.endUpdate();
                }
                return { success: true };
            }
            return { success: false, error: "GraphML import not available" };
        }
        catch (e) {
            return { success: false, error: e.message };
        }
    }
    toCompressedXml() {
        try {
            const ui = this._api.editorUi;
            if (!ui) {
                return this.toXml();
            }
            if (typeof ui.getFileData === "function") {
                const data = ui.getFileData(true);
                return { success: true, data };
            }
            return this.toXml();
        }
        catch (e) {
            return { success: false, error: e.message };
        }
    }
    fromCompressedXml(data) {
        try {
            const ui = this._api.editorUi;
            if (!ui) {
                return this.fromXml(data);
            }
            if (typeof ui.setFileData === "function") {
                ui.setFileData(data);
                return { success: true };
            }
            return this.fromXml(data);
        }
        catch (e) {
            return { success: false, error: e.message };
        }
    }
    validateXml(xml) {
        try {
            if (!xml || typeof xml !== "string") {
                return {
                    success: true,
                    data: { valid: false, error: "Invalid input: not a string" },
                };
            }
            const doc = mxUtils.parseXml(xml);
            const parseError = doc.getElementsByTagName("parsererror");
            if (parseError.length > 0) {
                return {
                    success: true,
                    data: { valid: false, error: "XML parsing error" },
                };
            }
            const root = doc.documentElement;
            if (!root) {
                return {
                    success: true,
                    data: { valid: false, error: "No root element" },
                };
            }
            const tagName = root.tagName || root.nodeName;
            if (tagName !== "mxGraphModel" && tagName !== "mxfile") {
                return {
                    success: true,
                    data: {
                        valid: false,
                        error: `Unexpected root element: ${tagName}. Expected mxGraphModel or mxfile`,
                    },
                };
            }
            return {
                success: true,
                data: { valid: true, rootElement: tagName },
            };
        }
        catch (e) {
            return { success: false, error: e.message };
        }
    }
}

// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0
const LIBRARIES = {
    AWS4: "aws4",
};
class LibraryManager {
    constructor(api) {
        this._api = api;
        this._libraries = {
            [LIBRARIES.AWS4]: {
                name: "AWS Architecture Icons (AWS4)",
                icons: AWS4_ICONS,
                groups: AWS4_GROUPS,
                colors: AWS4_COLORS,
                findIcon: findIcon,
                getCategories: getCategories,
                getIconsByCategory: getIconsByCategory,
                getGroupTypes: getGroupTypes,
                buildResourceIconStyle,
                buildProductIconStyle,
                buildGroupStyle,
            },
        };
    }
    getAvailableLibraries() {
        try {
            const libraries = Object.entries(this._libraries).map(([id, lib]) => ({
                id,
                name: lib.name,
                categories: lib.getCategories(),
            }));
            return { success: true, data: libraries };
        }
        catch (e) {
            return { success: false, error: e.message };
        }
    }
    getLibraryInfo(libraryId) {
        try {
            const lib = this._libraries[libraryId];
            if (!lib) {
                return { success: false, error: `Unknown library: ${libraryId}` };
            }
            return {
                success: true,
                data: {
                    id: libraryId,
                    name: lib.name,
                    categories: lib.getCategories(),
                    groupTypes: lib.getGroupTypes(),
                },
            };
        }
        catch (e) {
            return { success: false, error: e.message };
        }
    }
    findIcon(libraryId, iconName, category) {
        try {
            const lib = this._libraries[libraryId];
            if (!lib) {
                return { success: false, error: `Unknown library: ${libraryId}` };
            }
            const icon = lib.findIcon(iconName, category);
            if (!icon) {
                return { success: false, error: `Icon not found: ${iconName}` };
            }
            return { success: true, data: icon };
        }
        catch (e) {
            return { success: false, error: e.message };
        }
    }
    getIconsByCategory(libraryId, category) {
        try {
            const lib = this._libraries[libraryId];
            if (!lib) {
                return { success: false, error: `Unknown library: ${libraryId}` };
            }
            const icons = lib.getIconsByCategory(category);
            if (!icons) {
                return { success: false, error: `Unknown category: ${category}` };
            }
            return { success: true, data: icons };
        }
        catch (e) {
            return { success: false, error: e.message };
        }
    }
    getCategories(libraryId) {
        try {
            const lib = this._libraries[libraryId];
            if (!lib) {
                return { success: false, error: `Unknown library: ${libraryId}` };
            }
            return { success: true, data: lib.getCategories() };
        }
        catch (e) {
            return { success: false, error: e.message };
        }
    }
    getGroupTypes(libraryId) {
        try {
            const lib = this._libraries[libraryId];
            if (!lib) {
                return { success: false, error: `Unknown library: ${libraryId}` };
            }
            return { success: true, data: lib.getGroupTypes() };
        }
        catch (e) {
            return { success: false, error: e.message };
        }
    }
    buildIconStyle(libraryId, iconName, options = {}) {
        try {
            const lib = this._libraries[libraryId];
            if (!lib) {
                return { success: false, error: `Unknown library: ${libraryId}` };
            }
            const icon = lib.findIcon(iconName, options.category);
            const fillColor = options.fillColor || (icon ? icon.fillColor : undefined);
            const type = options.type || "resource";
            let style;
            if (type === "product") {
                style = lib.buildProductIconStyle(icon ? icon.icon : iconName, {
                    fillColor,
                });
            }
            else {
                style = lib.buildResourceIconStyle(icon ? icon.icon : iconName, {
                    fillColor,
                });
            }
            return { success: true, data: style };
        }
        catch (e) {
            return { success: false, error: e.message };
        }
    }
    buildGroupStyle(libraryId, groupType, options = {}) {
        try {
            const lib = this._libraries[libraryId];
            if (!lib) {
                return { success: false, error: `Unknown library: ${libraryId}` };
            }
            const style = lib.buildGroupStyle(groupType, options);
            return { success: true, data: style };
        }
        catch (e) {
            return { success: false, error: e.message };
        }
    }
    parseStyle(styleString) {
        try {
            const parsed = parseStyleString(styleString);
            // Filter out undefined values
            const result = {};
            for (const [key, value] of Object.entries(parsed)) {
                if (value !== undefined) {
                    result[key] = String(value);
                }
            }
            return { success: true, data: result };
        }
        catch (e) {
            return { success: false, error: e.message };
        }
    }
    buildStyle(styleObj) {
        try {
            const result = buildStyleString(styleObj);
            return { success: true, data: result };
        }
        catch (e) {
            return { success: false, error: e.message };
        }
    }
    getColors(libraryId) {
        try {
            const lib = this._libraries[libraryId];
            if (!lib) {
                return { success: false, error: `Unknown library: ${libraryId}` };
            }
            return { success: true, data: lib.colors || {} };
        }
        catch (e) {
            return { success: false, error: e.message };
        }
    }
    // AWS4 convenience methods
    getAwsIcon(iconName, category) {
        return this.findIcon(LIBRARIES.AWS4, iconName, category);
    }
    buildAwsIconStyle(iconName, options = {}) {
        return this.buildIconStyle(LIBRARIES.AWS4, iconName, options);
    }
    buildAwsGroupStyle(groupType, options = {}) {
        return this.buildGroupStyle(LIBRARIES.AWS4, groupType, options);
    }
}

// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0
/**
 * @file DrawioAPI.ts - Clean API Facade for draw.io
 * @description Provides programmatic control over draw.io diagrams.
 */
/**
 * Factory function to create a DrawioAPI instance.
 */
function createDrawioAPI(dependencies = {}) {
    return new DrawioAPI(dependencies);
}
/**
 * Main API class providing a facade over draw.io internals.
 */
class DrawioAPI {
    constructor(dependencies) {
        this._graph = dependencies.graph || null;
        this._model = dependencies.model || null;
        this._editorUi = dependencies.editorUi || null;
        // If graph is provided but model isn't, try to get model from graph
        if (this._graph &&
            !this._model &&
            typeof this._graph.getModel ===
                "function") {
            this._model = this._graph.getModel();
        }
        this.diagram = new DiagramManager(this);
        this.cells = new CellManager(this);
        this.styles = new StyleManager(this);
        this.io = new IOManager(this);
        this.libraries = new LibraryManager(this);
    }
    /**
     * Initialize the API with an existing EditorUi instance.
     */
    init(editorUi) {
        try {
            if (!editorUi) {
                return { success: false, error: "EditorUi is required" };
            }
            this._editorUi = editorUi;
            const ui = editorUi;
            if (ui.editor && ui.editor.graph) {
                this._graph = ui.editor.graph;
                this._model = this._graph.getModel();
            }
            return { success: true };
        }
        catch (e) {
            return { success: false, error: e.message };
        }
    }
    /**
     * Check if the API is properly initialized.
     */
    isInitialized() {
        return this._graph !== null && this._model !== null;
    }
    get graph() {
        return this._graph;
    }
    get model() {
        return this._model;
    }
    get editorUi() {
        return this._editorUi;
    }
    setGraph(graph) {
        this._graph = graph;
        if (graph &&
            typeof graph.getModel === "function") {
            this._model = graph.getModel();
        }
    }
    setModel(model) {
        this._model = model;
    }
    setEditorUi(editorUi) {
        this._editorUi = editorUi;
    }
    getVersion() {
        return {
            success: true,
            data: {
                api: "1.0.0",
                name: "DrawioAPI",
            },
        };
    }
    /**
     * Execute an operation within a transaction.
     */
    transaction(fn) {
        try {
            if (!this._model) {
                return { success: false, error: "API not initialized" };
            }
            const model = this._model;
            model.beginUpdate();
            try {
                const result = fn();
                return result !== undefined
                    ? result
                    : { success: true };
            }
            finally {
                model.endUpdate();
            }
        }
        catch (e) {
            return { success: false, error: e.message };
        }
    }
    insertVertex(options) {
        return this.cells.insertVertex(options);
    }
    insertEdge(options) {
        return this.cells.insertEdge(options);
    }
    createSvgDataUri(svgContent) {
        return this.cells.createSvgDataUri(svgContent);
    }
    createImageDataUri(imageData, mimeType) {
        return this.cells.createImageDataUri(imageData, mimeType);
    }
    insertImageVertex(options) {
        return this.cells.insertImageVertex(options);
    }
    toXml() {
        return this.io.toXml();
    }
    fromXml(xml) {
        return this.io.fromXml(xml);
    }
}
// For non-module environments, expose on window
if (typeof window !== "undefined") {
    window.createDrawioAPI = createDrawioAPI;
    window.DrawioAPI = DrawioAPI;
}

// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0
// =============================================================================
// LEGACY TYPES EXPORT (for compatibility)
// =============================================================================
/**
 * Types namespace for backwards compatibility.
 */
const Types = {
// This object exists for backwards compatibility with JS imports
};

// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0
class MockModel {
    constructor() {
        this._nextId = 2;
        this._updateLevel = 0;
        this._cells = new Map();
        this._root = this._createRootCell();
        this._defaultParent = this._createDefaultParent();
        this._root.children.push(this._defaultParent);
        this._cells.set("0", this._root);
        this._cells.set("1", this._defaultParent);
    }
    _createRootCell() {
        const cell = {
            id: "0",
            children: [],
            parent: null,
            value: null,
            geometry: null,
            style: null,
            vertex: false,
            edge: false,
            source: null,
            target: null,
            getId: () => "0",
            getValue: () => null,
            setValue: () => { },
            getParent: () => null,
            getGeometry: () => null,
            setGeometry: () => { },
            getStyle: () => "",
            setStyle: () => { },
            getChildCount: function () {
                return this.children.length;
            },
            getChildAt: function (i) {
                return this.children[i] || null;
            },
        };
        return cell;
    }
    _createDefaultParent() {
        const cell = {
            id: "1",
            children: [],
            parent: this._root,
            value: null,
            geometry: null,
            style: null,
            vertex: false,
            edge: false,
            source: null,
            target: null,
            getId: () => "1",
            getValue: () => null,
            setValue: () => { },
            getParent: () => this._root,
            getGeometry: () => null,
            setGeometry: () => { },
            getStyle: () => "",
            setStyle: () => { },
            getChildCount: function () {
                return this.children.length;
            },
            getChildAt: function (i) {
                return this.children[i] || null;
            },
        };
        return cell;
    }
    getRoot() {
        return this._root;
    }
    setRoot(root) {
        this._root = root;
        this._cells.clear();
        this._cells.set(root.id || root.getId(), root);
        if (root.children) {
            for (const child of root.children) {
                this._cells.set(child.id || child.getId(), child);
            }
        }
    }
    getCell(id) {
        return this._cells.get(id) || null;
    }
    getChildren(cell) {
        if (!cell)
            return [];
        return cell.children ? [...cell.children] : [];
    }
    isVertex(cell) {
        return (cell !== null &&
            typeof cell === "object" &&
            cell.vertex === true);
    }
    isEdge(cell) {
        return (cell !== null &&
            typeof cell === "object" &&
            cell.edge === true);
    }
    beginUpdate() {
        this._updateLevel++;
    }
    endUpdate() {
        this._updateLevel--;
    }
    getUpdateLevel() {
        return this._updateLevel;
    }
    clear() {
        this._defaultParent.children = [];
        this._cells.clear();
        this._cells.set("0", this._root);
        this._cells.set("1", this._defaultParent);
        this._nextId = 2;
    }
    add(parent, cell, index) {
        if (!cell.id) {
            cell.id = String(this._nextId++);
        }
        cell.parent = parent;
        if (!parent.children) {
            parent.children = [];
        }
        if (typeof index === "number") {
            parent.children.splice(index, 0, cell);
        }
        else {
            parent.children.push(cell);
        }
        this._cells.set(cell.id, cell);
        return cell;
    }
    remove(cell) {
        if (cell.parent && cell.parent.children) {
            const index = cell.parent.children.indexOf(cell);
            if (index >= 0) {
                cell.parent.children.splice(index, 1);
            }
        }
        this._cells.delete(cell.id);
        return cell;
    }
    setValue(cell, value) {
        if (cell) {
            cell.value = value;
        }
    }
    setGeometry(cell, geometry) {
        if (cell) {
            cell.geometry = geometry;
        }
    }
    setStyle(cell, style) {
        if (cell) {
            cell.style = style;
        }
    }
    getNextId() {
        return String(this._nextId++);
    }
}

// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0
/**
 * @file MockGraph.ts - Mock implementation of mxGraph
 * @description Provides a testable mock of mxGraph for unit testing
 */
class MockStylesheetImpl {
    constructor() {
        this._defaultVertexStyle = {};
        this._defaultEdgeStyle = {};
    }
    getDefaultVertexStyle() {
        return this._defaultVertexStyle;
    }
    getDefaultEdgeStyle() {
        return this._defaultEdgeStyle;
    }
}
class MockGraphViewImpl {
    constructor(graph) {
        this._states = new Map();
        this._graph = graph;
    }
    getState(cell) {
        if (!cell)
            return null;
        return (this._states.get(cell.id) || null);
    }
    setState(cell, state) {
        if (cell) {
            this._states.set(cell.id, state);
        }
    }
}
class MockGraph {
    constructor(model) {
        this._selection = [];
        this._model = model || new MockModel();
        this._stylesheet = new MockStylesheetImpl();
        this._view = new MockGraphViewImpl(this);
    }
    getModel() {
        return this._model;
    }
    getDefaultParent() {
        return this._model.getCell("1");
    }
    insertVertex(parent, id, value, x, y, width, height, style) {
        const cell = this._createCell(id, value, true, false);
        cell.geometry = {
            x: x || 0,
            y: y || 0,
            width: width || 0,
            height: height || 0,
            clone: function () {
                return { ...this };
            },
        };
        cell.style = style || "";
        this._model.add(parent || this.getDefaultParent(), cell);
        return cell;
    }
    insertEdge(parent, id, value, source, target, style) {
        const cell = this._createCell(id, value, false, true);
        cell.source = source;
        cell.target = target;
        cell.style = style || "";
        cell.geometry = {
            x: 0,
            y: 0,
            width: 0,
            height: 0,
            points: [],
            clone: function () {
                return { ...this, points: [...(this.points || [])] };
            },
        };
        this._model.add(parent || this.getDefaultParent(), cell);
        return cell;
    }
    _createCell(id, value, vertex, edge) {
        const cellId = id || this._model.getNextId();
        const cell = {
            id: cellId,
            value: value,
            geometry: null,
            style: "",
            vertex: vertex,
            edge: edge,
            parent: null,
            children: [],
            source: null,
            target: null,
            getId: function () {
                return this.id;
            },
            getValue: function () {
                return this.value;
            },
            setValue: function (v) {
                this.value = v;
            },
            getGeometry: function () {
                return this.geometry;
            },
            setGeometry: function (g) {
                this.geometry = g;
            },
            getStyle: function () {
                return this.style || "";
            },
            setStyle: function (s) {
                this.style = s;
            },
            getParent: function () {
                return this.parent;
            },
            getChildCount: function () {
                return this.children ? this.children.length : 0;
            },
            getChildAt: function (i) {
                return this.children ? this.children[i] : null;
            },
        };
        return cell;
    }
    removeCells(cells) {
        if (!cells)
            return [];
        for (const cell of cells) {
            if (cell.parent && cell.parent.children) {
                const index = cell.parent.children.indexOf(cell);
                if (index >= 0) {
                    cell.parent.children.splice(index, 1);
                }
            }
            this._model.remove(cell);
        }
        return cells;
    }
    cloneCells(cells) {
        if (!cells)
            return [];
        return cells.map((cell) => {
            const clone = this._createCell(null, cell.value || "", cell.vertex, cell.edge);
            if (cell.geometry) {
                clone.geometry = { ...cell.geometry, clone: cell.geometry.clone };
            }
            clone.style = cell.style;
            return clone;
        });
    }
    addCells(cells, parent) {
        if (!cells)
            return [];
        const targetParent = parent || this.getDefaultParent();
        for (const cell of cells) {
            this._model.add(targetParent, cell);
        }
        return cells;
    }
    groupCells(group, border, cells) {
        if (!cells || cells.length === 0) {
            throw new Error("No cells to group");
        }
        const groupCell = group || this._createCell(null, "", true, false);
        groupCell.geometry = {
            x: 0,
            y: 0,
            width: 100,
            height: 100,
            clone: function () {
                return { ...this };
            },
        };
        this._model.add(this.getDefaultParent(), groupCell);
        for (const cell of cells) {
            if (cell.parent && cell.parent.children) {
                const index = cell.parent.children.indexOf(cell);
                if (index >= 0) {
                    cell.parent.children.splice(index, 1);
                }
            }
            cell.parent = groupCell;
            groupCell.children.push(cell);
        }
        return groupCell;
    }
    ungroupCells(groups) {
        if (!groups)
            return [];
        const released = [];
        const defaultParent = this.getDefaultParent();
        for (const group of groups) {
            if (group.children) {
                for (const child of [...group.children]) {
                    child.parent = defaultParent;
                    defaultParent.children.push(child);
                    released.push(child);
                }
                group.children = [];
            }
            this._model.remove(group);
        }
        return released;
    }
    getEdges(cell, parent, incoming, outgoing) {
        const edges = [];
        const searchParent = parent || this.getDefaultParent();
        if (searchParent.children) {
            for (const child of searchParent.children) {
                if (child.edge) {
                    if (incoming && child.target === cell) {
                        edges.push(child);
                    }
                    if (outgoing && child.source === cell) {
                        edges.push(child);
                    }
                }
            }
        }
        return edges;
    }
    getGraphBounds() {
        const parent = this.getDefaultParent();
        if (!parent.children || parent.children.length === 0) {
            return null;
        }
        let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
        for (const cell of parent.children) {
            if (cell.geometry && cell.vertex) {
                const geo = cell.geometry;
                minX = Math.min(minX, geo.x);
                minY = Math.min(minY, geo.y);
                maxX = Math.max(maxX, geo.x + geo.width);
                maxY = Math.max(maxY, geo.y + geo.height);
            }
        }
        if (minX === Infinity)
            return null;
        return {
            x: minX,
            y: minY,
            width: maxX - minX,
            height: maxY - minY,
        };
    }
    getSelectionCells() {
        return this._selection;
    }
    setSelectionCells(cells) {
        this._selection = cells || [];
    }
    clearSelection() {
        this._selection = [];
    }
    getStylesheet() {
        return this._stylesheet;
    }
    getView() {
        return this._view;
    }
    getSvg() {
        if (typeof document !== "undefined") {
            const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
            svg.setAttribute("width", "100");
            svg.setAttribute("height", "100");
            return svg;
        }
        return null;
    }
}

// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0
function escapeXml(str) {
    if (!str)
        return "";
    return String(str)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&apos;");
}
class XmlSerializer {
    serialize(api, options = {}) {
        try {
            const diagramName = options.diagramName || "Page-1";
            const wrapInMxFile = options.wrapInMxFile !== false;
            const graphModelXml = this._serializeGraphModel(api);
            if (wrapInMxFile) {
                const fullXml = this._wrapInMxFile(graphModelXml, diagramName);
                return { success: true, data: fullXml };
            }
            return { success: true, data: graphModelXml };
        }
        catch (e) {
            return { success: false, error: e.message };
        }
    }
    _serializeGraphModel(api) {
        const model = api.model;
        const defaultParent = model.getCell("1");
        const cells = defaultParent ? model.getChildren(defaultParent) : [];
        let cellsXml = "";
        cellsXml += '      <mxCell id="0" />\n';
        cellsXml += '      <mxCell id="1" parent="0" />\n';
        for (const cell of cells) {
            cellsXml += this._serializeCell(cell);
        }
        return `<mxGraphModel dx="1426" dy="798" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="1100" pageHeight="850">
    <root>
${cellsXml}    </root>
  </mxGraphModel>`;
    }
    _serializeCell(cell) {
        const id = cell.id || (cell.getId ? cell.getId() : "");
        const value = escapeXml(cell.value || "");
        const style = cell.style || "";
        if (cell.vertex) {
            return this._serializeVertex(id, value, style, cell);
        }
        else if (cell.edge) {
            return this._serializeEdge(id, value, style, cell);
        }
        return "";
    }
    _serializeVertex(id, value, style, cell) {
        const geo = cell.geometry || {};
        const parentId = cell.parent
            ? cell.parent.id || (cell.parent.getId ? cell.parent.getId() : "1")
            : "1";
        let xml = `      <mxCell id="${escapeXml(id)}" value="${value}" style="${escapeXml(style)}" vertex="1" parent="${escapeXml(parentId)}">\n`;
        xml += `        <mxGeometry x="${geo.x || 0}" y="${geo.y || 0}" width="${geo.width || 100}" height="${geo.height || 50}" as="geometry" />\n`;
        xml += "      </mxCell>\n";
        return xml;
    }
    _serializeEdge(id, value, style, cell) {
        const sourceId = cell.source
            ? cell.source.id || (cell.source.getId ? cell.source.getId() : "")
            : "";
        const targetId = cell.target
            ? cell.target.id || (cell.target.getId ? cell.target.getId() : "")
            : "";
        const parentId = cell.parent
            ? cell.parent.id || (cell.parent.getId ? cell.parent.getId() : "1")
            : "1";
        let xml = `      <mxCell id="${escapeXml(id)}" value="${value}" style="${escapeXml(style)}" edge="1" parent="${escapeXml(parentId)}"`;
        if (sourceId)
            xml += ` source="${escapeXml(sourceId)}"`;
        if (targetId)
            xml += ` target="${escapeXml(targetId)}"`;
        xml += ">\n";
        const geo = cell.geometry;
        if (geo && geo.points && geo.points.length > 0) {
            xml += '        <mxGeometry relative="1" as="geometry">\n';
            xml += '          <Array as="points">\n';
            for (const point of geo.points) {
                xml += `            <mxPoint x="${point.x}" y="${point.y}" />\n`;
            }
            xml += "          </Array>\n";
            xml += "        </mxGeometry>\n";
        }
        else {
            xml += '        <mxGeometry relative="1" as="geometry" />\n';
        }
        xml += "      </mxCell>\n";
        return xml;
    }
    _wrapInMxFile(graphModelXml, diagramName) {
        const timestamp = new Date().toISOString();
        return `<mxfile host="drawio-jsapi" modified="${timestamp}" agent="DrawioJSAPI/1.0.0" version="1.0.0">
  <diagram id="diagram-1" name="${escapeXml(diagramName)}">
  ${graphModelXml}
  </diagram>
</mxfile>`;
    }
}

// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0
/**
 * @file XmlParser.ts - Parse .drawio XML files
 * @description Parses .drawio XML files into DrawioAPI model.
 */
class XmlParser {
    parse(xml, api) {
        try {
            const doc = new DOMParser().parseFromString(xml, "text/xml");
            const root = doc.documentElement;
            if (!root) {
                return { success: false, error: "Invalid XML: no root element" };
            }
            if (root.tagName === "mxfile") {
                return this._parseMxFile(root, api);
            }
            else if (root.tagName === "mxGraphModel") {
                return this._parseMxGraphModel(root, api);
            }
            return { success: false, error: `Unknown XML format: ${root.tagName}` };
        }
        catch (e) {
            return { success: false, error: e.message };
        }
    }
    _parseMxFile(mxfile, api) {
        const diagrams = mxfile.getElementsByTagName("diagram");
        if (diagrams.length === 0) {
            return { success: false, error: "No diagram found in mxfile" };
        }
        const diagram = diagrams[0];
        const diagramName = diagram.getAttribute("name") || "Page-1";
        let content = this._getTextContent(diagram).trim();
        if (!content) {
            return { success: false, error: "Empty diagram content" };
        }
        if (!content.startsWith("<")) {
            try {
                content = this._decompress(content);
            }
            catch (e) {
                return {
                    success: false,
                    error: `Failed to decompress diagram: ${e.message}`,
                };
            }
        }
        const innerDoc = new DOMParser().parseFromString(content, "text/xml");
        const graphModel = innerDoc.documentElement;
        if (!graphModel || graphModel.tagName !== "mxGraphModel") {
            return {
                success: false,
                error: "Invalid diagram content: expected mxGraphModel",
            };
        }
        const result = this._parseMxGraphModel(graphModel, api);
        if (result.success) {
            result.data = { diagramName, pageCount: diagrams.length };
        }
        return result;
    }
    _getTextContent(element) {
        if (element.textContent !== undefined) {
            return element.textContent;
        }
        let text = "";
        for (let i = 0; i < element.childNodes.length; i++) {
            const child = element.childNodes[i];
            if (child.nodeType === 3) {
                text += child.nodeValue || "";
            }
        }
        return text;
    }
    _decompress(encoded) {
        encoded = encoded.replace(/\s/g, "");
        const decoded = Buffer.from(encoded, "base64");
        const inflated = pako.inflateRaw(decoded, { to: "string" });
        return decodeURIComponent(inflated);
    }
    _parseMxGraphModel(graphModel, api) {
        const root = graphModel.getElementsByTagName("root")[0];
        if (!root) {
            return { success: false, error: "No root element in mxGraphModel" };
        }
        const cells = root.getElementsByTagName("mxCell");
        const cellMap = new Map();
        const edgesToProcess = [];
        for (let i = 0; i < cells.length; i++) {
            const cellNode = cells[i];
            const id = cellNode.getAttribute("id");
            if (id === "0" || id === "1")
                continue;
            const isVertex = cellNode.getAttribute("vertex") === "1";
            const isEdge = cellNode.getAttribute("edge") === "1";
            if (isVertex) {
                this._parseVertex(cellNode, api);
                if (id)
                    cellMap.set(id, true);
            }
            else if (isEdge) {
                edgesToProcess.push(cellNode);
            }
        }
        for (const cellNode of edgesToProcess) {
            this._parseEdge(cellNode, api);
        }
        return { success: true };
    }
    _parseVertex(cellNode, api) {
        const id = cellNode.getAttribute("id") || undefined;
        const value = cellNode.getAttribute("value") || "";
        const style = cellNode.getAttribute("style") || "";
        const parentId = cellNode.getAttribute("parent");
        const geoNode = cellNode.getElementsByTagName("mxGeometry")[0];
        const geometry = {
            x: parseFloat(geoNode?.getAttribute("x") || "0"),
            y: parseFloat(geoNode?.getAttribute("y") || "0"),
            width: parseFloat(geoNode?.getAttribute("width") || "100"),
            height: parseFloat(geoNode?.getAttribute("height") || "50"),
        };
        api.cells.insertVertex({
            id,
            label: value,
            geometry,
            style: this._parseStyleString(style),
            parentId: parentId !== "1" ? parentId || undefined : undefined,
        });
    }
    _parseEdge(cellNode, api) {
        const id = cellNode.getAttribute("id") || undefined;
        const value = cellNode.getAttribute("value") || "";
        const style = cellNode.getAttribute("style") || "";
        const sourceId = cellNode.getAttribute("source");
        const targetId = cellNode.getAttribute("target");
        if (!sourceId || !targetId) {
            return;
        }
        const waypoints = [];
        const geoNode = cellNode.getElementsByTagName("mxGeometry")[0];
        if (geoNode) {
            const arrayNode = geoNode.getElementsByTagName("Array")[0];
            if (arrayNode) {
                const points = arrayNode.getElementsByTagName("mxPoint");
                for (let i = 0; i < points.length; i++) {
                    waypoints.push({
                        x: parseFloat(points[i].getAttribute("x") || "0"),
                        y: parseFloat(points[i].getAttribute("y") || "0"),
                    });
                }
            }
        }
        api.cells.insertEdge({
            id,
            label: value,
            sourceId,
            targetId,
            style: this._parseStyleString(style),
            waypoints: waypoints.length > 0 ? waypoints : undefined,
        });
    }
    _parseStyleString(styleString) {
        if (!styleString)
            return {};
        const result = {};
        const pairs = styleString.split(";");
        for (const pair of pairs) {
            if (pair) {
                const eqIndex = pair.indexOf("=");
                if (eqIndex > 0) {
                    const key = pair.substring(0, eqIndex);
                    const value = pair.substring(eqIndex + 1);
                    result[key] = value;
                }
                else if (pair.trim()) {
                    result[pair.trim()] = "1";
                }
            }
        }
        return result;
    }
}

// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0
/**
 * @file DiagramEngine.ts - Wrapper around DrawioAPI
 * @description Manages DrawioAPI lifecycle and provides enhanced XML I/O.
 */
const logger = {
    info: (msg, data) => {
        if (process.env.DEBUG)
            console.log("[INFO]", msg, data ?? "");
    },
    error: (msg, data) => {
        console.error("[ERROR]", msg, data ?? "");
    },
};
class DiagramEngine {
    constructor() {
        this._model = null;
        this._graph = null;
        this._api = null;
        this._filePath = null;
        this._diagramName = "Page-1";
        this._serializer = new XmlSerializer();
        this._parser = new XmlParser();
    }
    create(options = {}) {
        try {
            this._model = new MockModel();
            this._graph = new MockGraph(this._model);
            this._api = createDrawioAPI({ graph: this._graph, model: this._model });
            this._filePath = null;
            this._diagramName = options.name || "Page-1";
            logger.info("Created new diagram", { name: this._diagramName });
            return {
                success: true,
                data: {
                    name: this._diagramName,
                    isNew: true,
                },
            };
        }
        catch (e) {
            logger.error("Failed to create diagram", { error: e.message });
            return { success: false, error: e.message };
        }
    }
    loadFromXml(xml) {
        try {
            this._model = new MockModel();
            this._graph = new MockGraph(this._model);
            this._api = createDrawioAPI({ graph: this._graph, model: this._model });
            const result = this._parser.parse(xml, this._api);
            if (result.success && result.data) {
                this._diagramName = result.data.diagramName || "Page-1";
            }
            if (result.success) {
                logger.info("Loaded diagram from XML", { name: this._diagramName });
            }
            return result;
        }
        catch (e) {
            logger.error("Failed to load diagram from XML", {
                error: e.message,
            });
            return { success: false, error: e.message };
        }
    }
    loadFromFile(filePath) {
        try {
            const xml = readFileSync(filePath, "utf8");
            const result = this.loadFromXml(xml);
            if (result.success) {
                this._filePath = filePath;
                logger.info("Loaded diagram from file", {
                    path: filePath,
                    name: this._diagramName,
                });
            }
            return result;
        }
        catch (e) {
            logger.error("Failed to load diagram from file", {
                path: filePath,
                error: e.message,
            });
            return {
                success: false,
                error: `Failed to read file: ${e.message}`,
            };
        }
    }
    toXml(options = {}) {
        if (!this._api) {
            return { success: false, error: "No diagram loaded" };
        }
        return this._serializer.serialize(this._api, {
            diagramName: options.diagramName || this._diagramName,
            wrapInMxFile: options.wrapInMxFile,
        });
    }
    saveToFile(filePath, options = {}) {
        const targetPath = filePath || this._filePath;
        if (!targetPath) {
            return { success: false, error: "No file path specified" };
        }
        const xmlResult = this.toXml(options);
        if (!xmlResult.success || !xmlResult.data) {
            return {
                success: false,
                error: xmlResult.error || "Failed to serialize XML",
            };
        }
        try {
            writeFileSync(targetPath, xmlResult.data, "utf8");
            this._filePath = targetPath;
            logger.info("Saved diagram to file", { path: targetPath });
            return {
                success: true,
                data: {
                    path: targetPath,
                    name: options.diagramName || this._diagramName,
                },
            };
        }
        catch (e) {
            logger.error("Failed to save diagram to file", {
                path: targetPath,
                error: e.message,
            });
            return {
                success: false,
                error: `Failed to write file: ${e.message}`,
            };
        }
    }
    getInfo() {
        if (!this._api) {
            return { success: false, error: "No diagram loaded" };
        }
        const info = this._api.diagram.getInfo();
        return {
            success: true,
            data: {
                name: this._diagramName,
                filePath: this._filePath,
                ...info.data,
            },
        };
    }
    clear() {
        if (!this._api) {
            return { success: false, error: "No diagram loaded" };
        }
        const result = this._api.diagram.clear();
        if (result.success) {
            logger.info("Cleared diagram");
        }
        return result;
    }
    get isLoaded() {
        return this._api !== null;
    }
    get api() {
        return this._api;
    }
    get filePath() {
        return this._filePath;
    }
    get diagramName() {
        return this._diagramName;
    }
    set diagramName(name) {
        this._diagramName = name;
    }
}

// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0
function setupGlobalMocks() {
    globalThis.mxConstants = {
        STYLE_FILLCOLOR: "fillColor",
        STYLE_STROKECOLOR: "strokeColor",
        STYLE_STROKEWIDTH: "strokeWidth",
        STYLE_FONTCOLOR: "fontColor",
        STYLE_FONTSIZE: "fontSize",
        STYLE_FONTFAMILY: "fontFamily",
        STYLE_FONTSTYLE: "fontStyle",
        STYLE_SHAPE: "shape",
        STYLE_ROUNDED: "rounded",
        STYLE_DASHED: "dashed",
        STYLE_OPACITY: "opacity",
        STYLE_ALIGN: "align",
        STYLE_VERTICAL_ALIGN: "verticalAlign",
        STYLE_VERTICAL_LABEL_POSITION: "verticalLabelPosition",
        STYLE_LABEL_POSITION: "labelPosition",
        STYLE_SPACING: "spacing",
        STYLE_SPACING_TOP: "spacingTop",
        STYLE_SPACING_RIGHT: "spacingRight",
        STYLE_SPACING_BOTTOM: "spacingBottom",
        STYLE_SPACING_LEFT: "spacingLeft",
        STYLE_PERIMETER: "perimeter",
        STYLE_EDGE: "edgeStyle",
        STYLE_ENDARROW: "endArrow",
        STYLE_STARTARROW: "startArrow",
        STYLE_ENDFILL: "endFill",
        STYLE_STARTFILL: "startFill",
        STYLE_GRADIENT_DIRECTION: "gradientDirection",
        STYLE_GRADIENTCOLOR: "gradientColor",
        STYLE_ASPECT: "aspect",
        STYLE_IMAGE: "image",
        STYLE_IMAGE_WIDTH: "imageWidth",
        STYLE_IMAGE_HEIGHT: "imageHeight",
        STYLE_WHITE_SPACE: "whiteSpace",
    };
    globalThis.mxUtils = {
        getXml: function (_node) {
            return "";
        },
        parseXml: function (_xml) {
            return null;
        },
    };
    globalThis.mxCodec = class {
        constructor(document) {
            this.document = document;
        }
        encode(model) {
            return { model, type: "mxGraphModel" };
        }
        decode(_node) {
            return null;
        }
    };
    globalThis.mxPoint = class {
        constructor(x = 0, y = 0) {
            this.x = x;
            this.y = y;
        }
        clone() {
            return new mxPoint(this.x, this.y);
        }
    };
    globalThis.mxRectangle = class {
        constructor(x = 0, y = 0, width = 0, height = 0) {
            this.x = x;
            this.y = y;
            this.width = width;
            this.height = height;
        }
        clone() {
            return new mxRectangle(this.x, this.y, this.width, this.height);
        }
    };
    globalThis.mxGeometry = class {
        constructor(x = 0, y = 0, width = 0, height = 0) {
            this.relative = false;
            this.points = null;
            this.offset = null;
            this.x = x;
            this.y = y;
            this.width = width;
            this.height = height;
        }
        clone() {
            const geo = new mxGeometry(this.x, this.y, this.width, this.height);
            geo.relative = this.relative;
            geo.points = this.points ? [...this.points] : null;
            geo.offset = this.offset;
            return geo;
        }
    };
}
// Auto-setup when module is imported
setupGlobalMocks();

// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0
/**
 * @file MockEditorUi.ts - Mock implementation of EditorUi
 * @description Provides a testable mock of EditorUi for unit testing
 */
class MockPage {
    constructor(id, name) {
        this._id = id;
        this._name = name;
    }
    getId() {
        return this._id;
    }
    getName() {
        return this._name;
    }
    setName(name) {
        this._name = name;
    }
}
class MockUndoManager {
    constructor() {
        this._history = [];
        this._index = -1;
    }
    undo() {
        if (this._index >= 0) {
            this._index--;
        }
    }
    redo() {
        if (this._index < this._history.length - 1) {
            this._index++;
        }
    }
    canUndo() {
        return this._index >= 0;
    }
    canRedo() {
        return this._index < this._history.length - 1;
    }
    add(edit) {
        this._history = this._history.slice(0, this._index + 1);
        this._history.push(edit);
        this._index = this._history.length - 1;
    }
}
class MockEditorUi {
    constructor(graph) {
        this._graph = graph || new MockGraph();
        this.editor = {
            graph: this._graph,
            undoManager: new MockUndoManager(),
        };
        this.pages = [new MockPage("page-1", "Page-1")];
        this.currentPage = this.pages[0];
    }
    get graph() {
        return this._graph;
    }
    insertPage(page, index) {
        const newPage = page ||
            new MockPage(`page-${this.pages.length + 1}`, `Page-${this.pages.length + 1}`);
        if (typeof index === "number") {
            this.pages.splice(index, 0, newPage);
        }
        else {
            this.pages.push(newPage);
        }
        return newPage;
    }
    removePage(page) {
        const index = this.pages.indexOf(page);
        if (index >= 0) {
            this.pages.splice(index, 1);
            if (this.currentPage === page && this.pages.length > 0) {
                this.currentPage = this.pages[0];
            }
        }
    }
    selectPage(page) {
        if (this.pages.includes(page)) {
            this.currentPage = page;
        }
    }
    getFileData(compressed) {
        const xml = "<mxfile><diagram>mock</diagram></mxfile>";
        return compressed ? xml : xml;
    }
    setFileData(_data) {
        // Mock implementation - just accept the data
    }
}

export { AWS4_BASE, AWS4_COLORS, AWS4_GROUPS, AWS4_ICONS, CellManager, DiagramEngine, DiagramManager, DrawioAPI, IOManager, LIBRARIES, LibraryManager, MockEditorUi, MockGraph, MockModel, MockPage, MockUndoManager, StyleManager, Types, XmlParser, XmlSerializer, buildGroupStyle, buildProductIconStyle, buildResourceIconStyle, buildStyleString, createDrawioAPI, findIcon, getCategories, getGroupTypes, getIconsByCategory, parseStyleString, setupGlobalMocks };
//# sourceMappingURL=drawio-jsapi.esm.js.map
