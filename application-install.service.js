"use strict";
Object.defineProperty(exports, "__esModule", {
    value: true
});
Object.defineProperty(exports, "ApplicationInstallService", {
    enumerable: true,
    get: function() {
        return ApplicationInstallService;
    }
});
const _common = require("@nestjs/common");
const _typeorm = require("@nestjs/typeorm");
const _fs = require("fs");
const _path = require("path");
const _types = require("twenty-shared/types");
const _utils = require("twenty-shared/utils");
const _typeorm1 = require("typeorm");
const _buildapplicationfilelistutil = require("./utils/build-application-file-list.util");
const _applicationmanifestapplyservice = require("../application-manifest/application-manifest-apply.service");
const _applicationsyncservice = require("../application-manifest/application-sync.service");
const _applicationpackagefetcherservice = require("../application-package/application-package-fetcher.service");
const _applicationversionvalidationservice = require("../application-package/application-version-validation.service");
const _versionreasontoexceptioncodeconstant = require("../application-package/constants/version-reason-to-exception-code.constant");
const _applicationregistrationentity = require("../application-registration/application-registration.entity");
const _applicationregistrationsourcetypeenum = require("../application-registration/enums/application-registration-source-type.enum");
const _isimagefilepathutil = require("../application-registration/utils/is-image-file-path.util");
const _applicationexception = require("../application.exception");
const _applicationservice = require("../application.service");
const _cachelockservice = require("../../cache-lock/cache-lock.service");
const _filestorageservice = require("../../file-storage/services/file-storage.service");
const _serverfilestorageservice = require("../../file-storage/services/server-file-storage.service");
const _mime = require("mime-types");
const _logicfunctionexecutorservice = require("../../logic-function/logic-function-executor/logic-function-executor.service");
const _logicfunctionqueueretrybackoffconstant = require("../../logic-function/logic-function-trigger/constants/logic-function-queue-retry-backoff.constant");
const _logicfunctiontriggerjob = require("../../logic-function/logic-function-trigger/jobs/logic-function-trigger.job");
const _messagequeuedecorator = require("../../message-queue/decorators/message-queue.decorator");
const _messagequeueconstants = require("../../message-queue/message-queue.constants");
const _messagequeueservice = require("../../message-queue/services/message-queue.service");
const _metricsservice = require("../../metrics/metrics.service");
const _metricskeystype = require("../../metrics/types/metrics-keys.type");
const _workspacecacheservice = require("../../../workspace-cache/services/workspace-cache.service");
function _ts_decorate(decorators, target, key, desc) {
    var c = arguments.length, r = c < 3 ? target : desc === null ? desc = Object.getOwnPropertyDescriptor(target, key) : desc, d;
    if (typeof Reflect === "object" && typeof Reflect.decorate === "function") r = Reflect.decorate(decorators, target, key, desc);
    else for(var i = decorators.length - 1; i >= 0; i--)if (d = decorators[i]) r = (c < 3 ? d(r) : c > 3 ? d(target, key, r) : d(target, key)) || r;
    return c > 3 && r && Object.defineProperty(target, key, r), r;
}
function _ts_metadata(k, v) {
    if (typeof Reflect === "object" && typeof Reflect.metadata === "function") return Reflect.metadata(k, v);
}
function _ts_param(paramIndex, decorator) {
    return function(target, key) {
        decorator(target, key, paramIndex);
    };
}
let ApplicationInstallService = class ApplicationInstallService {
    async installApplication(params) {
        const appRegistration = await this.appRegistrationRepository.findOne({
            where: {
                id: params.appRegistrationId
            }
        });
        if (!appRegistration) {
            throw new _applicationexception.ApplicationException(`Application registration with id ${params.appRegistrationId} not found`, _applicationexception.ApplicationExceptionCode.APPLICATION_NOT_FOUND);
        }
        if (appRegistration.sourceType === _applicationregistrationsourcetypeenum.ApplicationRegistrationSourceType.LOCAL) {
            this.logger.log(`Skipping install for LOCAL app ${appRegistration.universalIdentifier} (files synced by CLI watcher in dev mode)`);
            return true;
        }
        if (appRegistration.sourceType === _applicationregistrationsourcetypeenum.ApplicationRegistrationSourceType.OAUTH_ONLY) {
            this.logger.log(`Skipping install for OAUTH_ONLY app ${appRegistration.universalIdentifier} (OAuth-only clients have no code artifacts)`);
            return true;
        }
        const lockKey = `app-install:${params.workspaceId}:${appRegistration.universalIdentifier}`;
        return this.cacheLockService.withLock(()=>this.doInstallApplication(appRegistration, {
                version: params.version,
                workspaceId: params.workspaceId,
                skipWorkspaceCompatibilityCheck: params.skipWorkspaceCompatibilityCheck
            }), lockKey, {
            ttl: 60_000,
            ms: 500,
            maxRetries: 120
        });
    }
    async doInstallApplication(preLockAppRegistration, params) {
        // Re-read inside the lock so the authorization below cannot act on stale
        // listing or ownership state.
        const appRegistration = await this.appRegistrationRepository.findOne({
            where: {
                id: preLockAppRegistration.id
            }
        });
        if (!appRegistration) {
            throw new _applicationexception.ApplicationException(`Application registration with id ${preLockAppRegistration.id} not found`, _applicationexception.ApplicationExceptionCode.APPLICATION_NOT_FOUND);
        }
        // Tarball registrations that are neither listed nor pre-installed are
        // only installable by their owner workspace.
        if (appRegistration.sourceType === _applicationregistrationsourcetypeenum.ApplicationRegistrationSourceType.TARBALL && !appRegistration.isListed && !appRegistration.isPreInstalled && appRegistration.ownerWorkspaceId !== params.workspaceId) {
            throw new _applicationexception.ApplicationException(`Application registration ${appRegistration.universalIdentifier} is not available for this workspace`, _applicationexception.ApplicationExceptionCode.FORBIDDEN);
        }
        const resolvedPackage = await this.applicationPackageFetcherService.resolvePackage(appRegistration, {
            targetVersion: params.version
        });
        if (!resolvedPackage) {
            return true;
        }
        try {
            const existingApplication = await this.applicationService.findByUniversalIdentifier({
                universalIdentifier: appRegistration.universalIdentifier,
                workspaceId: params.workspaceId
            });
            return await this.runInstallWithMetrics({
                appRegistration,
                params,
                resolvedPackage,
                existingApplication
            });
        } finally{
            await this.applicationPackageFetcherService.cleanupExtractedDir(resolvedPackage.cleanupDir);
        }
    }
    async runInstallWithMetrics({ appRegistration, params, resolvedPackage, existingApplication }) {
        const isVersionUpgrade = (0, _utils.isDefined)(existingApplication);
        const attributes = {
            universal_identifier: appRegistration.universalIdentifier,
            app_name: resolvedPackage.manifest.application.displayName,
            source_type: appRegistration.sourceType,
            version: resolvedPackage.packageJson.version ?? 'unknown'
        };
        try {
            const result = await this.runInstall({
                appRegistration,
                params,
                resolvedPackage,
                existingApplication
            });
            this.metricsService.incrementCounterBy({
                key: isVersionUpgrade ? _metricskeystype.MetricsKeys.AppUpgradeSucceeded : _metricskeystype.MetricsKeys.AppInstallSucceeded,
                amount: 1,
                attributes
            });
            return result;
        } catch (error) {
            this.metricsService.incrementCounterBy({
                key: isVersionUpgrade ? _metricskeystype.MetricsKeys.AppUpgradeFailed : _metricskeystype.MetricsKeys.AppInstallFailed,
                amount: 1,
                attributes: {
                    ...attributes,
                    error_code: error instanceof _applicationexception.ApplicationException ? error.code : 'UNKNOWN'
                }
            });
            throw error;
        }
    }
    async runInstall({ appRegistration, params, resolvedPackage, existingApplication }) {
        const universalIdentifier = appRegistration.universalIdentifier;
        if (params.skipWorkspaceCompatibilityCheck !== true) {
            const requiredServerVersion = resolvedPackage.packageJson.engines?.['twenty'];
            const versionValidation = await this.applicationVersionValidationService.validateWorkspaceCompatibility({
                requiredServerVersion,
                workspaceId: params.workspaceId
            });
            if (!versionValidation.compatible) {
                throw new _applicationexception.ApplicationException(versionValidation.message, _versionreasontoexceptioncodeconstant.VERSION_REASON_TO_APPLICATION_EXCEPTION_CODE[versionValidation.reason]);
            }
        }
        const isVersionUpgrade = (0, _utils.isDefined)(existingApplication);
        const previousVersion = existingApplication?.version ?? undefined;
        const newVersion = resolvedPackage.packageJson.version;
        if (!(0, _utils.isDefined)(newVersion)) {
            throw new _applicationexception.ApplicationException(`Package ${universalIdentifier} has no version`, _applicationexception.ApplicationExceptionCode.PACKAGE_RESOLUTION_FAILED);
        }
        const application = await this.ensureApplicationExists({
            existingApplication,
            universalIdentifier,
            name: resolvedPackage.manifest.application.displayName,
            logo: resolvedPackage.manifest.application.logo ?? resolvedPackage.manifest.application.logoUrl ?? null,
            workspaceId: params.workspaceId,
            applicationRegistrationId: appRegistration.id,
            sourceType: appRegistration.sourceType
        });
        const incomingVersion = resolvedPackage.packageJson.version;
        // Rollback is scoped to the work after the application row exists: reaching
        // this catch means creation succeeded, so a fresh install (not an upgrade)
        // is the only case that needs uninstalling.
        try {
            if (isVersionUpgrade && (0, _utils.isDefined)(application.version) && (0, _utils.isDefined)(incomingVersion)) {
                const progression = this.applicationVersionValidationService.validateVersionProgression({
                    incomingVersion,
                    currentVersion: application.version,
                    universalIdentifier,
                    action: 'install'
                });
                if (!progression.allowed) {
                    throw new _applicationexception.ApplicationException(progression.message, _versionreasontoexceptioncodeconstant.VERSION_PROGRESSION_REASON_TO_INSTALL_EXCEPTION_CODE[progression.reason]);
                }
            }
            await this.writeFilesToStorage(resolvedPackage.extractedDir, resolvedPackage.manifest, universalIdentifier, params.workspaceId, appRegistration);
            const logoFileId = await this.importLogoFile({
                extractedDir: resolvedPackage.extractedDir,
                manifest: resolvedPackage.manifest,
                applicationUniversalIdentifier: universalIdentifier,
                workspaceId: params.workspaceId
            });
            if (application.logoFileId !== logoFileId) {
                await this.applicationService.update(application.id, {
                    logoFileId: logoFileId ?? null,
                    workspaceId: params.workspaceId
                });
            }
            await this.runPreInstallHook({
                manifest: resolvedPackage.manifest,
                workspaceId: params.workspaceId,
                applicationRegistrationId: appRegistration.id,
                previousVersion,
                newVersion,
                isVersionUpgrade,
                universalIdentifier
            });
            await this.applicationManifestApplyService.applyManifestToWorkspace({
                workspaceId: params.workspaceId,
                manifest: resolvedPackage.manifest,
                applicationRegistrationId: appRegistration.id,
                application,
                forceSdkClientGeneration: true
            });
            await this.runPostInstallHook({
                manifest: resolvedPackage.manifest,
                workspaceId: params.workspaceId,
                previousVersion,
                newVersion,
                isVersionUpgrade,
                universalIdentifier
            });
            await this.applicationManifestApplyService.refreshRegistrationFromManifest({
                applicationRegistrationId: appRegistration.id,
                manifest: resolvedPackage.manifest,
                latestAvailableVersion: newVersion,
                preventVersionDowngrade: true
            });
            this.logger.log(`Successfully installed app ${universalIdentifier} v${resolvedPackage.packageJson.version ?? 'unknown'}`);
            return true;
        } catch (error) {
            this.logger.error(`Failed to install app ${appRegistration.universalIdentifier}: ${error}`);
            if (!isVersionUpgrade) {
                // Rollback of a failed fresh install: the app never finished
                // installing, so the uninstall hook must not run.
                await this.applicationSyncService.uninstallApplication({
                    applicationUniversalIdentifier: universalIdentifier,
                    workspaceId: params.workspaceId,
                    shouldRunUninstallHook: false
                });
            }
            throw error;
        }
    }
    async runPreInstallHook(params) {
        const { manifest, workspaceId, applicationRegistrationId, previousVersion, newVersion, isVersionUpgrade, universalIdentifier } = params;
        if (!(0, _utils.isDefined)(manifest.application.preInstallLogicFunction)) {
            return;
        }
        await this.applicationSyncService.preInstallSynchronizeFromManifest({
            workspaceId: params.workspaceId,
            manifest,
            applicationRegistrationId
        });
        const { universalIdentifier: preInstallLogicFunctionUniversalIdentifier, shouldRunOnVersionUpgrade } = manifest.application.preInstallLogicFunction;
        if (isVersionUpgrade && !shouldRunOnVersionUpgrade) {
            this.logger.log(`Skipping pre-install hook for app ${universalIdentifier}: version upgrade and shouldRunOnVersionUpgrade is false`);
            return;
        }
        const { flatLogicFunctionMaps } = await this.workspaceCacheService.getOrRecompute(workspaceId, [
            'flatLogicFunctionMaps'
        ]);
        const flatLogicFunction = flatLogicFunctionMaps.byUniversalIdentifier[preInstallLogicFunctionUniversalIdentifier];
        // preInstallSynchronizeFromManifest should have registered this function
        // moments ago — a miss here means the pared-down sync did not persist the
        // entry, which is a real failure and should abort the install.
        if (!(0, _utils.isDefined)(flatLogicFunction)) {
            throw new _applicationexception.ApplicationException(`Pre-install logic function "${preInstallLogicFunctionUniversalIdentifier}" not found for application "${universalIdentifier}" after pre-install sync. The pared-down sync did not register the function as expected.`, _applicationexception.ApplicationExceptionCode.ENTITY_NOT_FOUND);
        }
        const payload = {
            previousVersion,
            newVersion
        };
        this.logger.log(`Executing pre-install hook for app ${universalIdentifier} with payload:`, JSON.stringify(payload));
        const result = await this.logicFunctionExecutorService.execute({
            logicFunctionId: flatLogicFunction.id,
            workspaceId,
            payload
        });
        if (!(0, _utils.isDefined)(result)) {
            this.logger.log('Pre-install hook executed successfully');
        }
        if (result.error) {
            throw new _applicationexception.ApplicationException(result.error.errorMessage, _applicationexception.ApplicationExceptionCode.PRE_INSTALL_ERROR);
        }
    }
    async runPostInstallHook(params) {
        const { manifest, workspaceId, previousVersion, newVersion, isVersionUpgrade, universalIdentifier } = params;
        if (!(0, _utils.isDefined)(manifest.application.postInstallLogicFunction)) {
            return;
        }
        const { universalIdentifier: postInstallLogicFunctionUniversalIdentifier, shouldRunOnVersionUpgrade, shouldRunSynchronously } = manifest.application.postInstallLogicFunction;
        if (isVersionUpgrade && !shouldRunOnVersionUpgrade) {
            this.logger.log(`Skipping post-install hook for app ${universalIdentifier}: version upgrade and shouldRunOnVersionUpgrade is false`);
            return;
        }
        const { flatLogicFunctionMaps } = await this.workspaceCacheService.getOrRecompute(workspaceId, [
            'flatLogicFunctionMaps'
        ]);
        const flatLogicFunction = flatLogicFunctionMaps.byUniversalIdentifier[postInstallLogicFunctionUniversalIdentifier];
        if (!(0, _utils.isDefined)(flatLogicFunction)) {
            throw new _applicationexception.ApplicationException(`Post-install logic function "${postInstallLogicFunctionUniversalIdentifier}" not found for application "${universalIdentifier}" after sync. Manifest may reference a stale identifier.`, _applicationexception.ApplicationExceptionCode.ENTITY_NOT_FOUND);
        }
        const payload = {
            previousVersion,
            newVersion
        };
        this.logger.log(`Enqueuing post-install hook for app ${universalIdentifier} with payload:`, JSON.stringify(payload));
        if (!shouldRunSynchronously) {
            await this.messageQueueService.add(_logicfunctiontriggerjob.LogicFunctionTriggerJob.name, {
                logicFunctionId: flatLogicFunction.id,
                workspaceId,
                payload
            }, {
                retryLimit: 3,
                backoff: _logicfunctionqueueretrybackoffconstant.LOGIC_FUNCTION_QUEUE_RETRY_BACKOFF
            });
            return;
        }
        const result = await this.logicFunctionExecutorService.execute({
            logicFunctionId: flatLogicFunction.id,
            workspaceId,
            payload
        });
        if (!(0, _utils.isDefined)(result)) {
            this.logger.log('Post-install hook executed successfully');
        }
        if (result.error) {
            throw new _applicationexception.ApplicationException(result.error.errorMessage, _applicationexception.ApplicationExceptionCode.POST_INSTALL_ERROR);
        }
    }
    resolveWithinDirOrThrow(extractedDir, relativePath) {
        const absolutePath = (0, _path.resolve)(extractedDir, relativePath);
        const relativeToDir = (0, _path.relative)(extractedDir, absolutePath);
        if (relativeToDir.startsWith('..') || (0, _path.isAbsolute)(relativeToDir)) {
            throw new _applicationexception.ApplicationException(`Path traversal detected for file: ${relativePath}`, _applicationexception.ApplicationExceptionCode.INVALID_INPUT);
        }
        return absolutePath;
    }
    async writeFilesToStorage(extractedDir, manifest, applicationUniversalIdentifier, workspaceId, appRegistration) {
        const filesToWrite = (0, _buildapplicationfilelistutil.buildApplicationFileList)(manifest);
        for (const { relativePath, fileFolder, isRequired } of filesToWrite){
            const absolutePath = this.resolveWithinDirOrThrow(extractedDir, relativePath);
            let content;
            try {
                content = await _fs.promises.readFile(absolutePath);
            } catch (error) {
                if (!isRequired && error instanceof Error && 'code' in error && error.code === 'ENOENT') {
                    this.logger.warn(`Source file not found in package: ${relativePath}; skipping for backward compatibility`);
                    continue;
                }
                throw new _applicationexception.ApplicationException(`File not found in package: ${relativePath}`, _applicationexception.ApplicationExceptionCode.PACKAGE_RESOLUTION_FAILED);
            }
            if (fileFolder === 'public-asset') {
                const mimeType = _mime.lookup(relativePath) || 'application/octet-stream';
                await this.serverFileStorageService.writeServerFile({
                    fileFolder: 'application-registration',
                    applicationRegistrationId: appRegistration.id,
                    resourcePath: relativePath,
                    contents: content,
                    mimeType
                });
            } else {
                await this.fileStorageService.writeFile({
                    sourceFile: content,
                    fileFolder,
                    applicationUniversalIdentifier,
                    workspaceId,
                    resourcePath: relativePath,
                    settings: {
                        isTemporaryFile: false,
                        toDelete: false
                    }
                });
            }
        }
    }
    async importLogoFile({ extractedDir, manifest, applicationUniversalIdentifier, workspaceId }) {
        const logo = manifest.application.logo ?? manifest.application.logoUrl;
        if (!(0, _utils.isDefined)(logo) || logo.startsWith('http://') || logo.startsWith('https://')) {
            return null;
        }
        if (!(0, _isimagefilepathutil.isImageFilePath)(logo)) {
            this.logger.warn(`Logo "${logo}" is not a supported image type; skipping logo import for ${applicationUniversalIdentifier}`);
            return null;
        }
        const absolutePath = this.resolveWithinDirOrThrow(extractedDir, logo);
        let content;
        try {
            content = await _fs.promises.readFile(absolutePath);
        } catch  {
            this.logger.warn(`Logo "${logo}" declared in manifest but not found in package for ${applicationUniversalIdentifier}; skipping logo import`);
            return null;
        }
        const file = await this.fileStorageService.writeFile({
            sourceFile: content,
            fileFolder: _types.FileFolder.PublicAsset,
            applicationUniversalIdentifier,
            workspaceId,
            resourcePath: logo,
            settings: {
                isTemporaryFile: false,
                toDelete: false
            }
        });
        return file.id;
    }
    async ensureApplicationExists(params) {
        if ((0, _utils.isDefined)(params.existingApplication)) {
            return params.existingApplication;
        }
        return await this.applicationService.create({
            universalIdentifier: params.universalIdentifier,
            name: params.name,
            logo: params.logo,
            sourcePath: params.universalIdentifier,
            sourceType: params.sourceType,
            applicationRegistrationId: params.applicationRegistrationId,
            workspaceId: params.workspaceId
        });
    }
    constructor(appRegistrationRepository, applicationService, applicationPackageFetcherService, applicationVersionValidationService, applicationSyncService, applicationManifestApplyService, fileStorageService, serverFileStorageService, logicFunctionExecutorService, cacheLockService, messageQueueService, workspaceCacheService, metricsService){
        this.appRegistrationRepository = appRegistrationRepository;
        this.applicationService = applicationService;
        this.applicationPackageFetcherService = applicationPackageFetcherService;
        this.applicationVersionValidationService = applicationVersionValidationService;
        this.applicationSyncService = applicationSyncService;
        this.applicationManifestApplyService = applicationManifestApplyService;
        this.fileStorageService = fileStorageService;
        this.serverFileStorageService = serverFileStorageService;
        this.logicFunctionExecutorService = logicFunctionExecutorService;
        this.cacheLockService = cacheLockService;
        this.messageQueueService = messageQueueService;
        this.workspaceCacheService = workspaceCacheService;
        this.metricsService = metricsService;
        this.logger = new _common.Logger(ApplicationInstallService.name);
    }
};
ApplicationInstallService = _ts_decorate([
    (0, _common.Injectable)(),
    _ts_param(0, (0, _typeorm.InjectRepository)(_applicationregistrationentity.ApplicationRegistrationEntity)),
    _ts_param(10, (0, _messagequeuedecorator.InjectMessageQueue)(_messagequeueconstants.MessageQueue.logicFunctionQueue)),
    _ts_metadata("design:type", Function),
    _ts_metadata("design:paramtypes", [
        typeof _typeorm1.Repository === "undefined" ? Object : _typeorm1.Repository,
        typeof _applicationservice.ApplicationService === "undefined" ? Object : _applicationservice.ApplicationService,
        typeof _applicationpackagefetcherservice.ApplicationPackageFetcherService === "undefined" ? Object : _applicationpackagefetcherservice.ApplicationPackageFetcherService,
        typeof _applicationversionvalidationservice.ApplicationVersionValidationService === "undefined" ? Object : _applicationversionvalidationservice.ApplicationVersionValidationService,
        typeof _applicationsyncservice.ApplicationSyncService === "undefined" ? Object : _applicationsyncservice.ApplicationSyncService,
        typeof _applicationmanifestapplyservice.ApplicationManifestApplyService === "undefined" ? Object : _applicationmanifestapplyservice.ApplicationManifestApplyService,
        typeof _filestorageservice.FileStorageService === "undefined" ? Object : _filestorageservice.FileStorageService,
        typeof _serverfilestorageservice.ServerFileStorageService === "undefined" ? Object : _serverfilestorageservice.ServerFileStorageService,
        typeof _logicfunctionexecutorservice.LogicFunctionExecutorService === "undefined" ? Object : _logicfunctionexecutorservice.LogicFunctionExecutorService,
        typeof _cachelockservice.CacheLockService === "undefined" ? Object : _cachelockservice.CacheLockService,
        typeof _messagequeueservice.MessageQueueService === "undefined" ? Object : _messagequeueservice.MessageQueueService,
        typeof _workspacecacheservice.WorkspaceCacheService === "undefined" ? Object : _workspacecacheservice.WorkspaceCacheService,
        typeof _metricsservice.MetricsService === "undefined" ? Object : _metricsservice.MetricsService
    ])
], ApplicationInstallService);

//# sourceMappingURL=application-install.service.js.map