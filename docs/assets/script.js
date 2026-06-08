/**
 * Logique principale de l'editeur de configuration TrendRadar
 * Particularite : preserve a 100% les commentaires et le format du YAML d'origine
 */

// Constantes de l'editeur
const EDITOR_LINE_HEIGHT = 19.5;  // Hauteur de ligne de l'editeur (px), utilisee pour le calcul du defilement

// ==========================================
// 0. Fonction de coloration des commentaires
// ==========================================

/**
 * Applique la coloration au texte ; ce qui suit # est affiche en gris
 */
function applyHighlight(text) {
    const escape = s => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    return text.split('\n').map(line => {
        const idx = line.indexOf('#');
        if (idx === -1) return escape(line);
        return escape(line.slice(0, idx)) + '<span class="syntax-comment">' + escape(line.slice(idx)) + '</span>';
    }).join('\n');
}

/**
 * Met a jour la couche de coloration
 */
function updateBackdrop(textareaId, backdropId) {
    const ta = document.getElementById(textareaId);
    const bd = document.getElementById(backdropId);
    if (ta && bd) bd.innerHTML = applyHighlight(ta.value) + '\n';
}

/**
 * Defilement synchronise
 */
function syncScroll(textareaId, backdropId) {
    const ta = document.getElementById(textareaId);
    const bd = document.getElementById(backdropId);
    if (ta && bd) {
        bd.scrollTop = ta.scrollTop;
        bd.scrollLeft = ta.scrollLeft;
    }
}

// ==========================================
// 12. Logique de la fenetre d'agrandissement du QR code
// ==========================================

const QR_MODAL_DATA = {
    weixin: {
        icon: '<i class="fa-brands fa-weixin text-green-600"></i>',
        iconBg: 'bg-green-100',
        title: 'Ne rien manquer',
        subtitle: 'Recevez les notifications de mise a jour en priorite',
        img: './assets/weixin.webp',
        alt: 'Compte officiel WeChat',
        hint: 'Scannez avec WeChat pour suivre le compte officiel'
    },
    donate: {
        icon: '<i class="fa-solid fa-hand-holding-heart text-emerald-600"></i>',
        iconBg: 'bg-emerald-100',
        title: 'Faire un don libre',
        subtitle: 'Montant libre, meme 1 yuan encourage (´▽`ʃ♡ƪ)',
        img: 'https://cdn-1258574687.cos.ap-shanghai.myqcloud.com/img/%2F2026%2F01%2F18ecce7c224ce0ea4c59394c29e408f8-e0d1db45.webp',
        alt: 'Paiement WeChat',
        hint: 'Scannez avec WeChat - montant libre'
    }
};

function openQrModal(type) {
    const data = QR_MODAL_DATA[type];
    if (!data) return;
    const modal = document.getElementById('qr-modal');
    document.getElementById('qr-modal-icon').className = 'w-10 h-10 rounded-xl flex items-center justify-center text-lg ' + data.iconBg;
    document.getElementById('qr-modal-icon').innerHTML = data.icon;
    document.getElementById('qr-modal-title').textContent = data.title;
    document.getElementById('qr-modal-subtitle').textContent = data.subtitle;
    document.getElementById('qr-modal-img').src = data.img;
    document.getElementById('qr-modal-img').alt = data.alt;
    document.getElementById('qr-modal-hint').textContent = data.hint;
    modal.classList.remove('hidden');
}

function closeQrModal() {
    const modal = document.getElementById('qr-modal');
    if (modal) modal.classList.add('hidden');
}

window.openQrModal = openQrModal;
window.closeQrModal = closeQrModal;
const MODULE_DEFS = [
    { id: 1, name: "1. Reglages de base", key: "app", editable: false },
    { id: 2, name: "2. Source de donnees - Plateformes de palmares", key: "platforms", editable: true },
    { id: 3, name: "3. Source de donnees - Abonnements RSS", key: "rss", editable: true },
    { id: 4, name: "4. Mode de rapport", key: "report", editable: true },
    { id: "4.5", name: "4.5 Strategie de filtrage", key: "filter", editable: true },
    { id: "4.6", name: "4.6 Filtrage intelligent par IA", key: "ai_filter", editable: true },
    { id: 5, name: "5. Controle du contenu des notifications", key: "display", editable: true },
    { id: 6, name: "6. Notifications", key: "notification", editable: true, partial: true },
    { id: 7, name: "7. Configuration du stockage", key: "storage", editable: false },
    { id: 8, name: "8. Configuration du modele IA", key: "ai", editable: true },
    { id: 9, name: "9. Fonction d'analyse IA", key: "ai_analysis", editable: true },
    { id: 10, name: "10. Fonction de traduction IA", key: "ai_translation", editable: true },
    { id: 11, name: "11. Reglages avances", key: "advanced", editable: false }
];

// Contenu par defaut initial (etat vide) - affiche seulement un texte d'aide
const INITIAL_YAML = `# Collez ici votre config.yaml...
# Ou glissez-deposez un fichier dans la zone d'edition
# Ou cliquez en haut a droite sur « Charger la derniere configuration officielle »`;

// Noms de cle LocalStorage
const STORAGE_KEY_CONFIG = 'trendradar_config_yaml';
const STORAGE_KEY_FREQUENCY = 'trendradar_frequency_txt';
const STORAGE_KEY_TIMELINE = 'trendradar_timeline_yaml';
const STORAGE_KEY_CONFIG_TIME = 'trendradar_config_time';
const STORAGE_KEY_FREQUENCY_TIME = 'trendradar_frequency_time';
const STORAGE_KEY_TIMELINE_TIME = 'trendradar_timeline_time';

// URL des fichiers de configuration officiels (source principale GitHub)
const GITHUB_RAW_BASE = 'https://raw.githubusercontent.com/sansan0/TrendRadar/refs/heads/master/';
const REMOTE_CONFIG_URL = GITHUB_RAW_BASE + 'config/config.yaml';
const REMOTE_FREQUENCY_URL = GITHUB_RAW_BASE + 'config/frequency_words.txt';
const REMOTE_TIMELINE_URL = GITHUB_RAW_BASE + 'config/timeline.yaml';
const REMOTE_VERSION_URL = GITHUB_RAW_BASE + 'version_configs';

// Toutes les sources (source principale GitHub + CDN de secours), par ordre de priorite
const ALL_SOURCES = [
    GITHUB_RAW_BASE,
    'https://fastly.jsdelivr.net/gh/sansan0/TrendRadar@master/',
    'https://cdn.jsdelivr.net/gh/sansan0/TrendRadar@master/',
    'https://gcore.jsdelivr.net/gh/sansan0/TrendRadar@master/',
];
let lastOkIndex = 0;

async function fetchWithTimeout(url, timeout = 5000) {
    const controller = new AbortController();
    const id = setTimeout(() => controller.abort(), timeout);
    try {
        const resp = await fetch(url, { signal: controller.signal });
        clearTimeout(id);
        return resp;
    } catch (e) {
        clearTimeout(id);
        throw e;
    }
}

async function fetchWithFallback(url, timeout = 5000) {
    const path = url.startsWith(GITHUB_RAW_BASE) ? url.slice(GITHUB_RAW_BASE.length) : null;
    if (!path) return fetch(url);

    const n = ALL_SOURCES.length;
    for (let offset = 0; offset < n; offset++) {
        const idx = (lastOkIndex + offset) % n;
        try {
            const resp = await fetchWithTimeout(ALL_SOURCES[idx] + path, timeout);
            if (resp.ok) {
                if (idx !== lastOkIndex) {
                    console.log(`[CDN] Bascule vers : ${ALL_SOURCES[idx].split('//')[1].split('/')[0]}`);
                }
                lastOkIndex = idx;
                return resp;
            }
        } catch {}
    }
    throw new Error('Aucune source disponible, verifiez votre connexion reseau');
}

let currentYaml = "";
let currentFrequency = "";
let currentTimeline = "";
let currentFrequencyData = null;  // Met en cache les donnees analysees pour eviter les desalignements d'index dus a une reanalyse
let currentTab = "config";

// ==========================================
// 2. Initialisation et liaison des evenements
// ==========================================
// Minuteur anti-rebond
let configSaveTimer = null;
let frequencySaveTimer = null;
let timelineSaveTimer = null;

document.addEventListener('DOMContentLoaded', () => {
    const yamlEditor = document.getElementById('yaml-editor');
    const frequencyEditor = document.getElementById('frequency-editor');

    // Tente de restaurer la configuration depuis LocalStorage
    const savedConfig = localStorage.getItem(STORAGE_KEY_CONFIG);
    const savedFrequency = localStorage.getItem(STORAGE_KEY_FREQUENCY);

    // Initialisation de l'editeur
    if (savedConfig && savedConfig.trim() && savedConfig !== INITIAL_YAML) {
        yamlEditor.value = savedConfig;
        currentYaml = savedConfig;
        showToast('Configuration precedemment enregistree restauree', 'info');
    } else {
        yamlEditor.value = INITIAL_YAML;
        currentYaml = INITIAL_YAML;
    }

    if (savedFrequency && savedFrequency.trim()) {
        frequencyEditor.value = savedFrequency;
        currentFrequency = savedFrequency;
    } else {
        frequencyEditor.value = "# Collez ici le contenu de votre frequency_words.txt...\n# Ou glissez-deposez un fichier dans la zone d'edition\n\n[GLOBAL_FILTER]\n\n[WORD_GROUPS]\n";
        currentFrequency = frequencyEditor.value;
    }

    // Initialisation de l'editeur Timeline
    const timelineEditor = document.getElementById('timeline-editor');
    const savedTimeline = localStorage.getItem(STORAGE_KEY_TIMELINE);

    const INITIAL_TIMELINE = `# Collez ici votre timeline.yaml...\n# Ou glissez-deposez un fichier dans la zone d'edition\n# Ou cliquez en haut a droite sur « Charger la derniere configuration officielle »`;

    if (savedTimeline && savedTimeline.trim() && savedTimeline !== INITIAL_TIMELINE) {
        timelineEditor.value = savedTimeline;
        currentTimeline = savedTimeline;
    } else {
        timelineEditor.value = INITIAL_TIMELINE;
        currentTimeline = INITIAL_TIMELINE;
    }

    // Affiche la liste des modules a droite
    renderModules();

    // Ecoute les saisies de l'editeur (synchronisation temps reel vers l'UI + enregistrement anti-rebond)
    yamlEditor.addEventListener('input', (e) => {
        currentYaml = e.target.value;
        updateBackdrop('yaml-editor', 'yaml-backdrop');
        syncYamlToUI();
        debounceSaveConfig();
    });

    frequencyEditor.addEventListener('input', (e) => {
        currentFrequency = e.target.value;
        updateBackdrop('frequency-editor', 'frequency-backdrop');
        currentFrequencyData = null;
        syncFrequencyToUI();
        debounceSaveFrequency();
    });

    timelineEditor.addEventListener('input', (e) => {
        currentTimeline = e.target.value;
        updateBackdrop('timeline-editor', 'timeline-backdrop');
        syncTimelineToUI();
        debounceSaveTimeline();
    });

    // Defilement synchronise
    yamlEditor.addEventListener('scroll', () => syncScroll('yaml-editor', 'yaml-backdrop'));
    frequencyEditor.addEventListener('scroll', () => syncScroll('frequency-editor', 'frequency-backdrop'));
    timelineEditor.addEventListener('scroll', () => syncScroll('timeline-editor', 'timeline-backdrop'));

    // Initialise la fonction de glisser-deposer
    initDragAndDrop(yamlEditor, 'config');
    initDragAndDrop(frequencyEditor, 'frequency');
    initDragAndDrop(timelineEditor, 'timeline');

    // Enregistre immediatement a la fermeture / au rafraichissement de la page
    window.addEventListener('beforeunload', saveAllToLocalStorage);

    document.addEventListener('keydown', function(e) {
        if ((e.ctrlKey || e.metaKey) && e.key === 's') {
            e.preventDefault();
            saveAllToLocalStorage();
            showToast('Configuration enregistree manuellement', 'success');
        }
    });

    syncYamlToUI();

    updateBackdrop('yaml-editor', 'yaml-backdrop');
    updateBackdrop('frequency-editor', 'frequency-backdrop');
    updateBackdrop('timeline-editor', 'timeline-backdrop');

    updateSaveTimeDisplay();
});

// Enregistrement anti-rebond de config.yaml
function debounceSaveConfig() {
    if (configSaveTimer) clearTimeout(configSaveTimer);
    configSaveTimer = setTimeout(() => {
        saveConfigToLocalStorage();
    }, 1000);
}

// Enregistrement anti-rebond de frequency_words.txt
function debounceSaveFrequency() {
    if (frequencySaveTimer) clearTimeout(frequencySaveTimer);
    frequencySaveTimer = setTimeout(() => {
        saveFrequencyToLocalStorage();
    }, 1000);
}

// Enregistrement anti-rebond de timeline.yaml
function debounceSaveTimeline() {
    if (timelineSaveTimer) clearTimeout(timelineSaveTimer);
    timelineSaveTimer = setTimeout(() => {
        saveTimelineToLocalStorage();
    }, 1000);
}

// ==========================================
// 2.1 Fonction de glisser-deposer
// ==========================================
function initDragAndDrop(editor, type) {
    const container = editor.parentElement;

    const dropOverlay = document.createElement('div');
    dropOverlay.className = 'drop-overlay hidden';
    dropOverlay.innerHTML = `
        <div class="drop-overlay-content">
            <i class="fa-solid fa-cloud-arrow-up text-4xl mb-2"></i>
            <div class="text-sm font-bold">Relachez pour charger le fichier</div>
            <div class="text-xs opacity-75">${type === 'config' ? 'config.yaml' : type === 'timeline' ? 'timeline.yaml' : 'frequency_words.txt'}</div>
        </div>
    `;
    container.style.position = 'relative';
    container.appendChild(dropOverlay);

    editor.addEventListener('dragover', (e) => {
        e.preventDefault();
        e.stopPropagation();
        dropOverlay.classList.remove('hidden');
    });

    editor.addEventListener('dragleave', (e) => {
        e.preventDefault();
        e.stopPropagation();
        if (!container.contains(e.relatedTarget)) {
            dropOverlay.classList.add('hidden');
        }
    });

    dropOverlay.addEventListener('dragleave', (e) => {
        e.preventDefault();
        e.stopPropagation();
        if (!container.contains(e.relatedTarget)) {
            dropOverlay.classList.add('hidden');
        }
    });

    dropOverlay.addEventListener('dragover', (e) => {
        e.preventDefault();
        e.stopPropagation();
    });

    dropOverlay.addEventListener('drop', (e) => {
        e.preventDefault();
        e.stopPropagation();
        dropOverlay.classList.add('hidden');
        handleFileDrop(e, type);
    });

    editor.addEventListener('drop', (e) => {
        e.preventDefault();
        e.stopPropagation();
        dropOverlay.classList.add('hidden');
        handleFileDrop(e, type);
    });
}

function handleFileDrop(e, type) {
    const files = e.dataTransfer.files;
    if (files.length === 0) return;

    const file = files[0];

    const validExtensions = type === 'config'
        ? ['.yaml', '.yml', '.txt']
        : type === 'timeline'
        ? ['.yaml', '.yml']
        : ['.txt', '.yaml', '.yml'];

    const fileName = file.name.toLowerCase();
    const isValid = validExtensions.some(ext => fileName.endsWith(ext));

    if (!isValid) {
        showToast(`Glissez un fichier ${type === 'config' || type === 'timeline' ? 'YAML' : 'TXT'}`, 'error');
        return;
    }

    const reader = new FileReader();
    reader.onload = (event) => {
        const content = event.target.result;

        if (type === 'config') {
            try {
                jsyaml.load(content);
                document.getElementById('yaml-editor').value = content;
                currentYaml = content;
                syncYamlToUI();
                showToast(`Charge : ${file.name}`, 'success');
            } catch (err) {
                showToast(`Erreur de syntaxe YAML : ${err.message}`, 'error');
                // On charge quand meme pour que l'utilisateur corrige
                document.getElementById('yaml-editor').value = content;
                currentYaml = content;
            }
        } else if (type === 'timeline') {
            try {
                jsyaml.load(content);
                document.getElementById('timeline-editor').value = content;
                currentTimeline = content;
                updateBackdrop('timeline-editor', 'timeline-backdrop');
                syncTimelineToUI();
                showToast(`Charge : ${file.name}`, 'success');
            } catch (err) {
                showToast(`Erreur de syntaxe YAML : ${err.message}`, 'error');
                document.getElementById('timeline-editor').value = content;
                currentTimeline = content;
            }
        } else {
            document.getElementById('frequency-editor').value = content;
            currentFrequency = content;
            syncFrequencyToUI();
            showToast(`Charge : ${file.name}`, 'success');
        }
    };

    reader.onerror = () => {
        showToast('Echec de lecture du fichier', 'error');
    };

    reader.readAsText(file);
}

// ==========================================
// 2.2 Enregistrement et restauration LocalStorage
// ==========================================

// Fonction generique d'enregistrement LocalStorage
function _saveToStorage(content, storageKey, timeKey, label) {
    try {
        if (content && content.trim().length > 10) {
            const now = new Date().toISOString();
            localStorage.setItem(storageKey, content);
            localStorage.setItem(timeKey, now);
            updateSaveTimeDisplay();
        }
    } catch (e) {
        console.warn(`Echec d'enregistrement LocalStorage de ${label} :`, e);
    }
}

function saveConfigToLocalStorage() {
    _saveToStorage(currentYaml, STORAGE_KEY_CONFIG, STORAGE_KEY_CONFIG_TIME, 'config');
}

function saveFrequencyToLocalStorage() {
    _saveToStorage(currentFrequency, STORAGE_KEY_FREQUENCY, STORAGE_KEY_FREQUENCY_TIME, 'frequency');
}

function saveTimelineToLocalStorage() {
    _saveToStorage(currentTimeline, STORAGE_KEY_TIMELINE, STORAGE_KEY_TIMELINE_TIME, 'timeline');
}

// Enregistre tout (appele a la fermeture de la page)
function saveAllToLocalStorage() {
    saveConfigToLocalStorage();
    saveFrequencyToLocalStorage();
    saveTimelineToLocalStorage();
}

// Compatibilite avec les anciens appels
function saveToLocalStorage() {
    saveAllToLocalStorage();
}

// Formatage de l'affichage de l'heure
function formatSaveTime(isoString) {
    if (!isoString) return 'Non enregistre';
    const date = new Date(isoString);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return "a l'instant";
    if (diffMins < 60) return `${diffMins} min`;
    if (diffHours < 24) return `${diffHours} h`;
    if (diffDays < 7) return `${diffDays} j`;

    return date.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}

// Met a jour l'affichage de l'heure d'enregistrement
function updateSaveTimeDisplay() {
    const configTime = localStorage.getItem(STORAGE_KEY_CONFIG_TIME);
    const frequencyTime = localStorage.getItem(STORAGE_KEY_FREQUENCY_TIME);

    // Met a jour l'affichage de l'heure pour config.yaml
    const configTimeEl = document.getElementById('config-save-time');
    const configLabelEl = document.getElementById('config-save-label');
    if (configTimeEl) {
        configTimeEl.textContent = formatSaveTime(configTime);
        configTimeEl.title = configTime ? new Date(configTime).toLocaleString('zh-CN') : 'Non enregistre';
        if (configLabelEl) {
            if (configTime) {
                configLabelEl.classList.remove('hidden');
            } else {
                configLabelEl.classList.add('hidden');
            }
        }
    }

    // Met a jour l'affichage de l'heure pour frequency_words.txt
    const frequencyTimeEl = document.getElementById('frequency-save-time');
    const frequencyLabelEl = document.getElementById('frequency-save-label');
    if (frequencyTimeEl) {
        frequencyTimeEl.textContent = formatSaveTime(frequencyTime);
        frequencyTimeEl.title = frequencyTime ? new Date(frequencyTime).toLocaleString('zh-CN') : 'Non enregistre';
        if (frequencyLabelEl) {
            if (frequencyTime) {
                frequencyLabelEl.classList.remove('hidden');
            } else {
                frequencyLabelEl.classList.add('hidden');
            }
        }
    }

    // Met a jour l'affichage de l'heure pour timeline.yaml
    const timelineTime = localStorage.getItem(STORAGE_KEY_TIMELINE_TIME);
    const timelineTimeEl = document.getElementById('timeline-save-time');
    const timelineLabelEl = document.getElementById('timeline-save-label');
    if (timelineTimeEl) {
        timelineTimeEl.textContent = formatSaveTime(timelineTime);
        timelineTimeEl.title = timelineTime ? new Date(timelineTime).toLocaleString('zh-CN') : 'Non enregistre';
        if (timelineLabelEl) {
            if (timelineTime) {
                timelineLabelEl.classList.remove('hidden');
            } else {
                timelineLabelEl.classList.add('hidden');
            }
        }
    }
}

// ==========================================
// 2.3 Charger la derniere configuration officielle
// ==========================================
window.openLoadConfigModal = function() {
    // Cree la fenetre de selection
    const modal = document.createElement('div');
    modal.id = 'load-config-modal';
    modal.className = 'modal-overlay';
    modal.innerHTML = `
        <div class="modal-content" style="max-width: 420px;">
            <div class="flex items-center justify-between mb-4">
                <h3 class="text-lg font-bold text-gray-800"><i class="fa-solid fa-cloud-arrow-down mr-2 text-blue-500"></i>Charger la derniere configuration officielle</h3>
                <button onclick="closeLoadConfigModal()" class="text-gray-400 hover:text-gray-600"><i class="fa-solid fa-times text-xl"></i></button>
            </div>
            <div class="text-sm text-gray-600 mb-4">
                Choisissez les fichiers de configuration a charger depuis GitHub :
            </div>
            <div class="space-y-3">
                <label class="flex items-center gap-3 p-3 rounded-lg border border-gray-200 hover:bg-blue-50 hover:border-blue-300 cursor-pointer transition-colors">
                    <input type="checkbox" id="load-config-yaml" checked class="w-4 h-4 text-blue-600 rounded">
                    <div class="flex-1">
                        <div class="font-medium text-gray-800">config.yaml</div>
                        <div class="text-xs text-gray-500">Configuration systeme, plateformes, IA, notifications, etc.</div>
                    </div>
                    <i class="fa-solid fa-file-code text-blue-400"></i>
                </label>
                <label class="flex items-center gap-3 p-3 rounded-lg border border-gray-200 hover:bg-blue-50 hover:border-blue-300 cursor-pointer transition-colors">
                    <input type="checkbox" id="load-frequency-txt" checked class="w-4 h-4 text-blue-600 rounded">
                    <div class="flex-1">
                        <div class="font-medium text-gray-800">frequency_words.txt</div>
                        <div class="text-xs text-gray-500">Groupes de mots-cles, regles de filtrage, logique regex</div>
                    </div>
                    <i class="fa-solid fa-filter text-orange-400"></i>
                </label>
                <label class="flex items-center gap-3 p-3 rounded-lg border border-gray-200 hover:bg-blue-50 hover:border-blue-300 cursor-pointer transition-colors">
                    <input type="checkbox" id="load-timeline-yaml" checked class="w-4 h-4 text-blue-600 rounded">
                    <div class="flex-1">
                        <div class="font-medium text-gray-800">timeline.yaml</div>
                        <div class="text-xs text-gray-500">Planification temporelle, modeles predefinis, plages horaires personnalisees</div>
                    </div>
                    <i class="fa-solid fa-calendar-week text-purple-400"></i>
                </label>
            </div>
            <div class="text-xs text-gray-400 mt-3 p-2 bg-gray-50 rounded">
                <i class="fa-solid fa-info-circle mr-1"></i>
                Source des donnees : <a href="https://github.com/sansan0/TrendRadar" target="_blank" class="text-blue-500 hover:underline">sansan0/TrendRadar</a>
            </div>
            <div class="flex justify-end gap-2 mt-4">
                <button onclick="closeLoadConfigModal()" class="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded-lg">Annuler</button>
                <button onclick="confirmLoadConfig()" class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700">
                    <i class="fa-solid fa-download mr-1"></i>Charger la selection
                </button>
            </div>
        </div>
    `;
    document.body.appendChild(modal);
}

window.closeLoadConfigModal = function() {
    const modal = document.getElementById('load-config-modal');
    if (modal) modal.remove();
}

window.confirmLoadConfig = async function() {
    const loadConfig = document.getElementById('load-config-yaml')?.checked;
    const loadFrequency = document.getElementById('load-frequency-txt')?.checked;
    const loadTimeline = document.getElementById('load-timeline-yaml')?.checked;

    if (!loadConfig && !loadFrequency && !loadTimeline) {
        showToast('Selectionnez au moins un fichier', 'warning');
        return;
    }

    closeLoadConfigModal();
    showToast('Chargement de la derniere configuration...', 'info');

    try {
        const promises = [];
        if (loadConfig) promises.push(fetchWithFallback(REMOTE_CONFIG_URL).then(r => ({ type: 'config', res: r })));
        if (loadFrequency) promises.push(fetchWithFallback(REMOTE_FREQUENCY_URL).then(r => ({ type: 'frequency', res: r })));
        if (loadTimeline) promises.push(fetchWithFallback(REMOTE_TIMELINE_URL).then(r => ({ type: 'timeline', res: r })));

        const results = await Promise.all(promises);

        for (const { type, res } of results) {
            if (!res.ok) {
                const names = { config: 'config.yaml', frequency: 'frequency_words.txt', timeline: 'timeline.yaml' };
                throw new Error(`${names[type]} : echec du chargement : ${res.status}`);
            }

            const text = await res.text();

            if (type === 'config') {
                try {
                    jsyaml.load(text);
                } catch (yamlErr) {
                    showToast(`Erreur de syntaxe YAML : ${yamlErr.message}`, 'error');
                    continue;
                }
                document.getElementById('yaml-editor').value = text;
                currentYaml = text;
                updateBackdrop('yaml-editor', 'yaml-backdrop');
                syncYamlToUI();
            } else if (type === 'timeline') {
                try {
                    jsyaml.load(text);
                } catch (yamlErr) {
                    showToast(`Erreur de syntaxe YAML : ${yamlErr.message}`, 'error');
                    continue;
                }
                document.getElementById('timeline-editor').value = text;
                currentTimeline = text;
                updateBackdrop('timeline-editor', 'timeline-backdrop');
                syncTimelineToUI();
            } else {
                document.getElementById('frequency-editor').value = text;
                currentFrequency = text;
                currentFrequencyData = null;
                updateBackdrop('frequency-editor', 'frequency-backdrop');
                syncFrequencyToUI();
            }
        }

        saveToLocalStorage();

        const loadedFiles = [];
        if (loadConfig) loadedFiles.push('config.yaml');
        if (loadFrequency) loadedFiles.push('frequency_words.txt');
        if (loadTimeline) loadedFiles.push('timeline.yaml');
        showToast(`Charge : ${loadedFiles.join(', ')}`, 'success');

    } catch (err) {
        console.error('Echec du chargement de la configuration distante :', err);
        showToast(`Echec du chargement : ${err.message}`, 'error');
    }
}

// ==========================================
// 2.4 Notification toast
// ==========================================
function showToast(message, type = 'info') {
    // Retire le toast existant
    const existingToast = document.querySelector('.toast-notification');
    if (existingToast) existingToast.remove();

    const toast = document.createElement('div');
    toast.className = `toast-notification toast-${type}`;

    const icons = {
        success: 'fa-check-circle',
        error: 'fa-times-circle',
        info: 'fa-info-circle',
        warning: 'fa-exclamation-triangle'
    };

    toast.innerHTML = `
        <i class="fa-solid ${icons[type] || icons.info}"></i>
        <span>${message}</span>
    `;

    document.body.appendChild(toast);

    // Animation d'entree
    requestAnimationFrame(() => {
        toast.classList.add('show');
    });

    // Disparition automatique
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// ==========================================
// 3. Logique de rendu
// ==========================================
function renderModules() {
    const container = document.getElementById('config-panel');
    container.innerHTML = '';

    renderModuleNav();

    MODULE_DEFS.forEach(mod => {
        const card = document.createElement('div');
        card.className = `module-card ${mod.editable ? 'active' : 'disabled'}`;
        card.id = `module-${mod.key}`;

        const header = `
            <div class="module-header px-4 py-3 flex items-center justify-between cursor-pointer" onclick="scrollToModuleInEditor('${mod.key}')">
                <div class="flex items-center">
                    <span class="text-sm font-bold">${mod.name}</span>
                    <i class="fa-solid fa-arrow-up-right-from-square text-blue-400 text-[10px] ml-2 opacity-0 group-hover:opacity-100" title="Aller a l'editeur de gauche"></i>
                </div>
                ${!mod.editable ?
                    '<span class="locked-badge text-[10px] text-gray-400 border border-gray-200 px-1.5 py-0.5 rounded">Lecture seule (editez a gauche)</span>' :
                    '<i class="fa-solid fa-chevron-down text-gray-400 text-xs"></i>'}
            </div>
        `;

        const body = mod.editable ? `<div class="module-body p-5 border-t border-gray-50 space-y-4" id="controls-${mod.key}"></div>` : '';

        card.innerHTML = header + body;
        container.appendChild(card);

        if (mod.editable) {
            renderControls(mod);
        }
    });
}

// Affiche la barre de navigation des modules
function renderModuleNav() {
    const nav = document.getElementById('module-nav');
    if (!nav) return;

    nav.innerHTML = MODULE_DEFS.map(mod => `
        <button onclick="scrollToModuleInEditor('${mod.key}')"
                class="module-nav-btn text-[10px] px-2 py-1 rounded ${mod.editable ? 'bg-blue-100 text-blue-700 hover:bg-blue-200' : 'bg-gray-100 text-gray-500 hover:bg-gray-200'} transition-colors"
                title="Aller au module ${mod.id}">
            ${mod.id}
        </button>
    `).join('');
}

// Bascule l'etat d'edition du nom de groupe
window.toggleGroupNameEdit = function(btn) {
    const container = btn.parentNode;
    const span = container.querySelector('span.text-sm');
    const input = container.querySelector('input[type="text"]');

    if (input.classList.contains('hidden')) {
        // Passe en mode edition
        span.classList.add('hidden');
        input.classList.remove('hidden');
        input.focus();
        btn.innerHTML = '<i class="fa-solid fa-check text-green-600"></i>';
    } else {
        // Quitte le mode edition
        span.classList.remove('hidden');
        input.classList.add('hidden');
        btn.innerHTML = '<i class="fa-solid fa-pen"></i>';

        // Si le contenu a change, la mise a jour est deja declenchee par onchange
        span.textContent = input.value;
    }
}

// Va a l'emplacement du groupe de mots correspondant dans l'editeur de gauche
window.scrollToWordGroupInEditor = function(groupIndex) {
    const editor = document.getElementById('frequency-editor');
    // Reanalyse pour garantir l'exactitude des numeros de ligne
    const data = parseFrequencyText(editor.value);

    if (!data.wordGroups[groupIndex]) return;

    const targetLineIndex = data.wordGroups[groupIndex].startLine;
    if (targetLineIndex === undefined || targetLineIndex === -1) return;

    const lines = editor.value.split('\n');
    const lineHeight = EDITOR_LINE_HEIGHT;
    const scrollPosition = targetLineIndex * lineHeight;

    // Definit la selection du curseur
    let charCount = 0;
    for (let i = 0; i < targetLineIndex; i++) {
        charCount += lines[i].length + 1; // +1 for newline
    }

    editor.focus();
    editor.setSelectionRange(charCount, charCount + lines[targetLineIndex].length);
    editor.scrollTop = scrollPosition - 50;

    // Effet de surbrillance
    editor.style.transition = 'background-color 0.3s';
    const originalBg = editor.style.backgroundColor;
    editor.style.backgroundColor = '#2d4a7c';
    setTimeout(() => {
        editor.style.backgroundColor = originalBg;
    }, 300);
}

// Va a l'emplacement du module correspondant dans l'editeur de gauche
window.scrollToModuleInEditor = function(modKey) {
    const editor = document.getElementById('yaml-editor');
    const yaml = editor.value;
    const lines = yaml.split('\n');

    // Recherche la ligne de commentaire titre du module (# N. nom du module)
    let targetLineIndex = -1;
    const mod = MODULE_DEFS.find(m => m.key === modKey);
    if (!mod) return;

    // Correspond directement a la ligne de titre contenant le numero du module, compatible avec les formats « 4. » et « 4.5 »
    const escapedId = String(mod.id).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const moduleTitlePattern = new RegExp(`^#\\s*${escapedId}(?:\\.)?\\s+`, 'i');

    for (let i = 0; i < lines.length; i++) {
        const line = lines[i];
        // Correspond a la ligne de titre du module (ligne de commentaire avec numero)
        if (moduleTitlePattern.test(line)) {
            targetLineIndex = i;
            break;
        }
    }

    // Si aucune ligne de titre trouvee, tente de chercher la cle du module (ex. platforms:)
    if (targetLineIndex === -1) {
        for (let i = 0; i < lines.length; i++) {
            if (lines[i].match(new RegExp(`^${modKey}:\\s*`))) {
                targetLineIndex = i;
                break;
            }
        }
    }

    if (targetLineIndex === -1) return;

    // Calcule la position cible et fait defiler
    const lineHeight = EDITOR_LINE_HEIGHT;
    const scrollPosition = targetLineIndex * lineHeight;

    // Definit la position du curseur
    const textBeforeTarget = lines.slice(0, targetLineIndex).join('\n').length + (targetLineIndex > 0 ? 1 : 0);
    editor.focus();
    editor.setSelectionRange(textBeforeTarget, textBeforeTarget + lines[targetLineIndex].length);

    editor.scrollTop = scrollPosition - 5;

    // Indication par surbrillance (effet de clignotement)
    editor.style.transition = 'background-color 0.3s';
    const originalBg = editor.style.backgroundColor;
    editor.style.backgroundColor = '#2d4a7c';
    setTimeout(() => {
        editor.style.backgroundColor = originalBg;
    }, 300);
}

function renderControls(mod) {
    const body = document.getElementById(`controls-${mod.key}`);

    // Definit differents controles d'UI selon la cle du module
    let html = "";

    switch(mod.key) {
        case "platforms":
            html = createToggleControl(mod.key, "enabled", "Activer la collecte des palmares");
            html += `<div class="mt-4 mb-2 text-xs font-bold text-gray-700">Liste des plateformes <span class="text-gray-400 font-normal">(reordonnable par glisser-deposer)</span></div>`;
            html += `<div id="platforms-list" class="space-y-2"></div>`;
            html += `<div class="flex items-center gap-2 mt-3">
                        <button onclick="openPlatformModal()" class="text-xs bg-green-600 text-white px-3 py-1.5 rounded hover:bg-green-700 transition-colors">
                            <i class="fa-solid fa-plus mr-1"></i>Ajouter une plateforme
                        </button>
                        <a href="https://github.com/sansan0/TrendRadar?tab=readme-ov-file#%E9%85%8D%E7%BD%AE%E8%AF%A6%E8%A7%A3" target="_blank" class="text-xs bg-gray-100 text-gray-600 px-3 py-1.5 rounded hover:bg-gray-200 transition-colors border border-gray-200 flex items-center gap-1 no-underline">
                            <i class="fa-solid fa-circle-question text-gray-400"></i>Ajouter une autre plateforme
                        </a>
                     </div>`;
            break;
        case "rss":
            html = createToggleControl(mod.key, "enabled", "Activer la collecte RSS");
            html += `<div class="mt-3 mb-2 text-xs font-bold text-gray-700">Filtre de fraicheur</div>`;
            html += createToggleControl(mod.key, "freshness_filter.enabled", "Activer le filtre de fraicheur");
            html += createNumberControl(mod.key, "freshness_filter.max_age_days", "Age maximal des articles (jours)");
            html += `<div class="mt-4 mb-2 text-xs font-bold text-gray-700">Liste des sources RSS</div>`;
            html += `<div id="rss-feeds-list" class="space-y-2"></div>`;
            html += `<div class="flex items-center gap-2 mt-3">
                        <button onclick="openRssModal()" class="text-xs bg-green-600 text-white px-3 py-1.5 rounded hover:bg-green-700 transition-colors">
                            <i class="fa-solid fa-plus mr-1"></i>Ajouter une source RSS
                        </button>
                        <div class="text-xs text-gray-500 italic">
                            (bibliotheque de references RSS incluse)
                        </div>
                     </div>`;
            html += `<div class="text-xs text-orange-600 mt-2 p-2 bg-orange-50 rounded border border-orange-200">
                        <i class="fa-solid fa-triangle-exclamation mr-1"></i>
                        <strong>Attention : </strong>Certains medias etrangers peuvent aborder des sujets sensibles ; le modele IA peut refuser de les traduire ou de les analyser. Selectionnez vos abonnements selon vos besoins reels.
                     </div>`;
            break;
        case "report":
            html = createSelectControl(mod.key, "mode", "Mode de rapport", ["current", "daily", "incremental"]);
            html += createSelectControl(mod.key, "display_mode", "Critere de regroupement", ["keyword", "platform"]);
            html += createToggleControl(mod.key, "sort_by_position_first", "Trier selon l'ordre de definition");
            html += createNumberControl(mod.key, "rank_threshold", "Seuil de surbrillance du classement");
            html += createNumberControl(mod.key, "max_news_per_keyword", "Nombre maximal d'elements affiches par mot-cle");
            break;
        case "filter":
            html = createSelectControl(mod.key, "method", "Methode de filtrage", ["keyword", "ai"]);
            html += createToggleControl(mod.key, "priority_sort_enabled", "En mode IA, trier par priorite des etiquettes");
            html += `<div class="text-xs text-gray-500 mt-2 p-2 bg-blue-50 rounded border border-blue-200">
                        <i class="fa-solid fa-info-circle mr-1 text-blue-500"></i>
                        <strong>Explication : </strong><code>method=keyword</code> utilise <code>frequency_words.txt</code> ;
                        <code>method=ai</code> utilise <code>ai_interests.txt</code> + AI et la configuration de filtrage IA.<br>
                        <code>priority_sort_enabled</code> ne s'applique qu'en <code>method=ai</code>.
                     </div>`;
            break;
        case "ai_filter":
            html = `<div class="text-xs text-gray-500 mb-3 p-2 bg-blue-50 rounded border border-blue-200">
                        <i class="fa-solid fa-info-circle mr-1 text-blue-500"></i>
                        Ne s'applique que lorsque <strong>filter.method=ai</strong>.
                    </div>`;
            html += createNumberControl(mod.key, "batch_size", "Nombre de titres par lot");
            html += createNumberControl(mod.key, "batch_interval", "Intervalle entre lots (secondes)");
            html += createNumberControl(mod.key, "min_score", "Seuil de score minimal (0 a 1)");
            html += createInputControl(mod.key, "interests_file", "Fichier de description des centres d'interet (optionnel)");
            html += `<div class="text-xs text-amber-700 mt-1 mb-3 p-2 bg-amber-50 rounded border border-amber-200">
                        <i class="fa-solid fa-folder-tree mr-1"></i>
                        Si vide, utilise <code>config/ai_interests.txt</code> ; si renseigne, recherche uniquement
                        <code>config/custom/ai/</code> ce nom de fichier.
                     </div>`;
            html += createNumberControl(mod.key, "reclassify_threshold", "Seuil de reclassement complet (0 a 1)");
            html += createInputControl(mod.key, "prompt_file", "Fichier de prompt de classification");
            html += createInputControl(mod.key, "extract_prompt_file", "Fichier de prompt d'extraction d'etiquettes");
            html += createInputControl(mod.key, "update_tags_prompt_file", "Fichier de prompt de mise a jour d'etiquettes");
            break;
        case "display":
            html = `<div class="text-xs font-bold text-gray-700 mb-2">Controle du contenu des notifications <span class="text-gray-400 font-normal">(reordonnable par glisser-deposer)</span></div>`;
            html += `<div id="display-regions-list" class="space-y-2"></div>`;
            html += `<div class="text-xs text-gray-500 mt-2 mb-6">
                        <i class="fa-solid fa-lightbulb mr-1"></i>
                        Astuce : l'ordre de la liste determine l'ordre d'affichage dans le rapport
                     </div>`;

            // Standalone Configuration Section
            html += `<div class="border-t border-gray-200 pt-4 mt-4">`;
            html += `<div class="text-xs font-bold text-gray-700 mb-3">Configuration de la zone autonome <span class="text-gray-400 font-normal">(l'affichage des notifications est controle par l'interrupteur ci-dessus, l'analyse IA est controlee independamment par l'interrupteur du module IA)</span></div>`;

            html += createNumberControl(mod.key, "standalone.max_items", "Nombre maximal d'elements affiches par source");

            html += `<div class="mt-3 mb-2 text-xs font-medium text-gray-700">Choisir les plateformes de palmares a afficher</div>`;
            html += `<div id="standalone-platforms-list" class="max-h-40 overflow-y-auto border border-gray-200 rounded p-2 bg-gray-50 grid grid-cols-2 gap-2"></div>`;

            html += `<div class="mt-3 mb-2 text-xs font-medium text-gray-700">Choisir les sources RSS a afficher</div>`;
            html += `<div id="standalone-rss-list" class="max-h-40 overflow-y-auto border border-gray-200 rounded p-2 bg-gray-50 grid grid-cols-1 gap-2"></div>`;

            html += `</div>`;

            setTimeout(() => {
                renderDisplayRegionsList();
                renderStandaloneLists();
            }, 0);
            break;
        case "notification":
            html = `<div class="text-xs text-gray-500 mb-2 p-2 bg-blue-50 rounded border border-blue-200">
                        <i class="fa-solid fa-info-circle mr-1 text-blue-500"></i>
                        L'heure des notifications est controlee par <strong>timeline.yaml</strong> ; passez a l'onglet timeline.yaml pour editer visuellement les regles de planification.<br>
                        Ici, on configure uniquement les canaux de notification (Telegram / WeChat Entreprise, etc.) ; modifiez-les dans l'editeur de gauche.
                    </div>`;
            break;
        case "ai":
            html = createInputControl(mod.key, "model", "Nom du modele");
            html += createInputControl(mod.key, "api_key", "API Key", "password");
            html += createInputControl(mod.key, "api_base", "URL de base de l'API (optionnel)");
            html += createNumberControl(mod.key, "timeout", "Delai d'expiration des requetes (secondes)");
            html += createNumberControl(mod.key, "temperature", "Temperature d'echantillonnage (0.0-2.0)");
            html += createNumberControl(mod.key, "max_tokens", "Nombre maximal de tokens generes");
            break;
        case "ai_analysis":
            html = createToggleControl(mod.key, "enabled", "Activer le rapport d'analyse IA");

            // Astuce : la fenetre temporelle d'analyse a ete deplacee vers timeline.yaml
            html += `<div class="text-xs text-gray-500 mt-3 mb-3 p-2 bg-blue-50 rounded border border-blue-200">
                        <i class="fa-solid fa-info-circle mr-1 text-blue-500"></i>
                        L'heure d'execution de l'analyse IA est desormais controlee par <strong>timeline.yaml</strong> de maniere centralisee.
                    </div>`;

            // Autres reglages de l'analyse IA
            html += `<div class="text-xs font-bold text-blue-600 mb-2">Configuration du contenu de l'analyse</div>`;
            html += createInputControl(mod.key, "language", "Langue de sortie");
            html += createInputControl(mod.key, "prompt_file", "Fichier de configuration du prompt");
            html += createSelectControl(mod.key, "mode", "Mode d'analyse IA", ["follow_report", "daily", "current", "incremental"]);
            html += createNumberControl(mod.key, "max_news_for_analysis", "Nombre maximal d'elements analyses");
            html += createToggleControl(mod.key, "include_rss", "Inclure le contenu RSS");
            html += createToggleControl(mod.key, "include_standalone", "Inclure les donnees de la zone autonome");
            html += createToggleControl(mod.key, "include_rank_timeline", "Transmettre la chronologie complete du classement");
            break;
        case "ai_translation":
            html = createToggleControl(mod.key, "enabled", "Activer la traduction automatique par IA");
            html += createInputControl(mod.key, "language", "Langue cible");
            html += createInputControl(mod.key, "prompt_file", "Fichier de configuration du prompt");
            break;
    }

    body.innerHTML = html;

    // Liaison des evenements
    body.querySelectorAll('input, select').forEach(el => {
        el.addEventListener('change', (e) => {
            updateYamlFromUI(mod.key, e.target.dataset.path, e.target);
        });
    });
}

// ==========================================
// 4. Logique de synchronisation (YAML -> UI)
// ==========================================
function syncYamlToUI() {
    try {
        const doc = jsyaml.load(currentYaml);
        if (!doc) return;

        MODULE_DEFS.filter(m => m.editable).forEach(mod => {
            const modData = doc[mod.key];
            if (!modData) return;

            const controls = document.querySelectorAll(`#controls-${mod.key} [data-path]`);
            controls.forEach(ctrl => {
                const path = ctrl.dataset.path.split('.');
                let val = modData;
                for (const part of path) {
                    val = val ? val[part] : undefined;
                }

                if (ctrl.type === 'checkbox') {
                    ctrl.checked = !!val;
                } else {
                    ctrl.value = val !== undefined ? val : "";
                }
            });
        });

        renderPlatformsList();
        renderRssFeedsList();
        renderStandaloneLists(); 
    } catch (e) {
        // En cas d'echec d'analyse, ne pas mettre a jour l'UI et conserver l'etat actuel
    }
}

// ==========================================
// 5. Logique de mise a jour (UI -> YAML) - point cle : preserver les commentaires via regex
// ==========================================
function updateYamlFromUI(modKey, path, el) {
    let newVal = el.type === 'checkbox' ? el.checked : el.value;

    // S'il s'agit d'un type numerique
    if (el.type === 'number') {
        newVal = parseFloat(newVal);
        if (isNaN(newVal)) newVal = 0;
    }

    const editor = document.getElementById('yaml-editor');
    let yaml = editor.value;
    const lines = yaml.split('\n');
    const pathParts = path.split('.');

    // Trouve la ligne de debut du module
    let moduleStartLine = -1;
    let moduleEndLine = lines.length;

    for (let i = 0; i < lines.length; i++) {
        const line = lines[i];
        // Correspond au debut du module (cle: sans indentation)
        const moduleMatch = line.match(/^([a-z_]+):/);
        if (moduleMatch) {
            if (moduleMatch[1] === modKey) {
                moduleStartLine = i;
            } else if (moduleStartLine >= 0) {
                // Module suivant trouve, on enregistre la fin du module actuel
                moduleEndLine = i;
                break;
            }
        }
    }

    if (moduleStartLine < 0) return;

    // Recherche le chemin cible dans le module
    let targetLine = -1;
    let currentIndent = 0;
    let searchKey = pathParts[pathParts.length - 1];

    for (let i = moduleStartLine + 1; i < moduleEndLine; i++) {
        const line = lines[i];
        if (line.trim() === '' || line.trim().startsWith('#')) continue;

        // Verifie si la cle cible correspond
        const indent = line.search(/\S/);
        const keyMatch = line.match(/^\s*([a-z_]+):\s*(.*)/i);

        if (keyMatch && keyMatch[1] === searchKey) {
            // Si le chemin est imbrique, verifier que le niveau d'indentation est correct
            if (pathParts.length > 1) {
                // Traitement simplifie : pour un chemin imbrique, s'assurer d'etre sous le bon parent
                let valid = true;
                for (let j = 0; j < pathParts.length - 1; j++) {
                    let found = false;
                    for (let k = moduleStartLine + 1; k < i; k++) {
                        const parentMatch = lines[k].match(/^\s*([a-z_]+):/i);
                        if (parentMatch && parentMatch[1] === pathParts[j]) {
                            found = true;
                            break;
                        }
                    }
                    if (!found) {
                        valid = false;
                        break;
                    }
                }
                if (!valid) continue;
            }

            targetLine = i;
            break;
        }
    }

    if (targetLine < 0) {
        // Permet d'ajouter un champ de premier niveau au module (ex. ai_filter.interests_file, commente par defaut)
        if (pathParts.length === 1) {
            let formattedVal = newVal;
            if (typeof newVal === 'string') {
                formattedVal = `"${newVal.replace(/"/g, '\\"')}"`;
            }

            lines.splice(moduleEndLine, 0, `  ${searchKey}: ${formattedVal}`);
            editor.value = lines.join('\n');
            currentYaml = editor.value;
            updateBackdrop('yaml-editor', 'yaml-backdrop');
            debounceSaveConfig();
        }
        return;
    }

    // Met a jour la ligne en preservant les commentaires
    const originalLine = lines[targetLine];
    const match = originalLine.match(/^(\s*[a-z_]+:\s*)(.*)$/i);

    if (match) {
        const prefix = match[1];
        const rest = match[2];

        // Extrait le commentaire existant
        const commentMatch = rest.match(/(\s*#.*)$/);
        const comment = commentMatch ? commentMatch[1] : '';

        // Formate la nouvelle valeur
        let formattedVal = newVal;
        if (typeof newVal === 'string') {
            // Recupere la valeur d'origine (sans le commentaire)
            const valPart = rest.slice(0, rest.length - comment.length).trim();
            // Verifie si la valeur d'origine comporte des guillemets
            const isOriginalQuoted = (valPart.startsWith('"') && valPart.endsWith('"')) ||
                                     (valPart.startsWith("'") && valPart.endsWith("'"));

            // Si la valeur d'origine a des guillemets, ou si la nouvelle valeur contient des caracteres speciaux (espace, deux-points, diese, guillemet) ou est vide, on ajoute des guillemets doubles
            if (isOriginalQuoted || newVal.includes(':') || newVal.includes('#') ||
                newVal.includes('"') || newVal.includes(' ') || newVal === "") {
                formattedVal = `"${newVal.replace(/"/g, '\\"')}"`;
            }
        }

        // Construit la nouvelle ligne
        lines[targetLine] = `${prefix}${formattedVal}${comment}`;
    }

    // Met a jour l'editeur
    editor.value = lines.join('\n');
    currentYaml = editor.value;
    updateBackdrop('yaml-editor', 'yaml-backdrop');
    debounceSaveConfig();
}

// ==========================================
// 6. Fabrique de composants d'UI
// ==========================================
function createToggleControl(mod, path, label) {
    const id = `toggle-${mod}-${path.replace('.', '-')}`;
    return `
        <div class="flex items-center justify-between">
            <label for="${id}" class="text-xs font-medium text-gray-700">${label}</label>
            <div class="relative inline-block w-10 mr-2 align-middle select-none">
                <input type="checkbox" id="${id}" data-path="${path}" class="toggle-checkbox absolute block w-5 h-5 rounded-full bg-white border-4 appearance-none cursor-pointer transition-all duration-200 ease-in-out"/>
                <label for="${id}" class="toggle-label block overflow-hidden h-5 rounded-full bg-gray-300 cursor-pointer"></label>
            </div>
        </div>
    `;
}

function createInputControl(mod, path, label, type = "text") {
    return `
        <div>
            <label class="block text-[10px] uppercase tracking-wider font-bold text-gray-400 mb-1">${label}</label>
            <input type="${type}" data-path="${path}" class="bg-white border-gray-300 focus:border-blue-500" placeholder="Non defini">
        </div>
    `;
}

function createNumberControl(mod, path, label) {
    return `
        <div class="flex items-center justify-between">
            <label class="text-xs font-medium text-gray-700">${label}</label>
            <input type="number" data-path="${path}" class="w-20 text-right bg-white border-gray-300" style="width: 80px">
        </div>
    `;
}

function createSelectControl(mod, path, label, options) {
    const optionsHtml = options.map(opt => `<option value="${opt}">${opt}</option>`).join('');
    return `
        <div>
            <label class="block text-[10px] uppercase tracking-wider font-bold text-gray-400 mb-1">${label}</label>
            <select data-path="${path}" class="bg-white border-gray-300">
                ${optionsHtml}
            </select>
        </div>
    `;
}

// ==========================================
// 7. Fonctions utilitaires
// ==========================================

window.copyResult = function() {
    const yamlEditor = document.getElementById('yaml-editor');
    const frequencyEditor = document.getElementById('frequency-editor');
    const timelineEditor = document.getElementById('timeline-editor');
    const editor = currentTab === 'config' ? yamlEditor : currentTab === 'timeline' ? timelineEditor : frequencyEditor;

    const text = editor.value;
    const btn = document.querySelector('button[onclick="copyResult()"]');
    const original = btn.innerHTML;

    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(() => {
            btn.innerHTML = '<i class="fa-solid fa-check mr-1.5"></i>Copie !';
            setTimeout(() => btn.innerHTML = original, 2000);
        }).catch(() => {
            editor.select();
            document.execCommand('copy');
            btn.innerHTML = '<i class="fa-solid fa-check mr-1.5"></i>Copie !';
            setTimeout(() => btn.innerHTML = original, 2000);
        });
    } else {
        editor.select();
        document.execCommand('copy');
        btn.innerHTML = '<i class="fa-solid fa-check mr-1.5"></i>Copie !';
        setTimeout(() => btn.innerHTML = original, 2000);
    }
}

window.resetToDefault = function() {
    if (confirm("Voulez-vous reinitialiser a l'etat initial ? Les modifications non enregistrees seront perdues.")) {
        if (currentTab === 'config') {
            const yamlEditor = document.getElementById('yaml-editor');
            yamlEditor.value = INITIAL_YAML;
            currentYaml = INITIAL_YAML;
            updateBackdrop('yaml-editor', 'yaml-backdrop');
            localStorage.removeItem(STORAGE_KEY_CONFIG);
            localStorage.removeItem(STORAGE_KEY_CONFIG_TIME);
            renderModules();
            syncYamlToUI();
            updateSaveTimeDisplay();
        } else if (currentTab === 'timeline') {
            const timelineEditor = document.getElementById('timeline-editor');
            const initialTimeline = `# Collez ici votre timeline.yaml...\n# Ou glissez-deposez un fichier dans la zone d'edition\n# Ou cliquez en haut a droite sur « Charger la derniere configuration officielle »`;
            timelineEditor.value = initialTimeline;
            currentTimeline = initialTimeline;
            updateBackdrop('timeline-editor', 'timeline-backdrop');
            localStorage.removeItem(STORAGE_KEY_TIMELINE);
            localStorage.removeItem(STORAGE_KEY_TIMELINE_TIME);
            syncTimelineToUI();
            updateSaveTimeDisplay();
        } else {
            const frequencyEditor = document.getElementById('frequency-editor');
            frequencyEditor.value = "# Collez ici le contenu de votre frequency_words.txt...\n\n[GLOBAL_FILTER]\n\n[WORD_GROUPS]\n";
            currentFrequency = frequencyEditor.value;
            updateBackdrop('frequency-editor', 'frequency-backdrop');
            localStorage.removeItem(STORAGE_KEY_FREQUENCY);
            localStorage.removeItem(STORAGE_KEY_FREQUENCY_TIME);
            syncFrequencyToUI();
            updateSaveTimeDisplay();
        }
        showToast("Reinitialise a l'etat initial", 'success');
    }
}

// ==========================================
// 8. Fonction de bascule des onglets
// ==========================================
window.switchTab = function(tab) {
    currentTab = tab;

    const activeClass = "tab-button active px-4 py-2 text-xs font-bold text-gray-300 hover:bg-[#2d2d30] transition-colors border-b-2 border-blue-500";
    const inactiveClass = "tab-button px-4 py-2 text-xs font-bold text-gray-500 hover:bg-[#2d2d30] transition-colors border-b-2 border-transparent";

    // Met a jour l'etat des boutons d'onglet
    const configBtn = document.getElementById('tab-config');
    const freqBtn = document.getElementById('tab-frequency');
    const timelineBtn = document.getElementById('tab-timeline');

    configBtn.className = tab === 'config' ? activeClass : inactiveClass;
    freqBtn.className = tab === 'frequency' ? activeClass : inactiveClass;
    timelineBtn.className = tab === 'timeline' ? activeClass : inactiveClass;

    // Met a jour l'affichage de l'editeur
    document.getElementById('yaml-editor-wrap').classList.toggle('hidden', tab !== 'config');
    document.getElementById('frequency-editor-wrap').classList.toggle('hidden', tab !== 'frequency');
    document.getElementById('timeline-editor-wrap').classList.toggle('hidden', tab !== 'timeline');

    // Met a jour le panneau de droite
    document.getElementById('config-panel').classList.toggle('hidden', tab !== 'config');
    document.getElementById('frequency-panel').classList.toggle('hidden', tab !== 'frequency');
    document.getElementById('timeline-panel').classList.toggle('hidden', tab !== 'timeline');

    // Met a jour l'affichage de la barre de navigation : visible uniquement en mode config
    const moduleNav = document.getElementById('module-nav');
    if (moduleNav) {
        moduleNav.classList.toggle('hidden', tab !== 'config');
    }

    // Met a jour l'affichage de l'heure d'enregistrement
    const saveTimeConfig = document.getElementById('save-time-config');
    const saveTimeFrequency = document.getElementById('save-time-frequency');
    const saveTimeTimeline = document.getElementById('save-time-timeline');
    if (saveTimeConfig) saveTimeConfig.classList.toggle('hidden', tab !== 'config');
    if (saveTimeFrequency) saveTimeFrequency.classList.toggle('hidden', tab !== 'frequency');
    if (saveTimeTimeline) saveTimeTimeline.classList.toggle('hidden', tab !== 'timeline');

    // Met a jour le titre de droite
    const versionBtn = document.getElementById('version-check-btn');
    if (tab === 'config') {
        document.getElementById('right-panel-title').textContent = 'Modules de configuration';
        if (versionBtn) { versionBtn.style.display = ''; versionBtn.title = "Verifier la version de config.yaml"; }
    } else if (tab === 'frequency') {
        document.getElementById('right-panel-title').textContent = 'Edition des mots de frequence';
        if (versionBtn) { versionBtn.style.display = ''; versionBtn.title = "Verifier la version de frequency_words.txt"; }
    } else {
        document.getElementById('right-panel-title').textContent = 'Planification temporelle';
        if (versionBtn) versionBtn.style.display = 'none';
    }

    if (tab === 'frequency') {
        renderFrequencyPanel();
    }
    if (tab === 'timeline') {
        syncTimelineToUI();
    }
}

// ==========================================
// 9. Fonctions de l'editeur Frequency
// ==========================================
function parseFrequencyText(text) {
    const result = {
        globalFilter: [],
        wordGroups: [],
        originalText: text  // Conserve le texte d'origine
    };

    const lines = text.split('\n');
    let currentSection = null;
    let currentGroup = null;
    let lastLineWasAlias = false;  // Indique si la ligne precedente etait une ligne d'alias
    let relatedGroupsBuffer = [];  // Met en cache les groupes lies consecutifs
    let pendingComments = [];  // Met en cache les lignes de commentaire a attribuer

    // Fonction utilitaire : enregistre les groupes lies en cache
    function flushRelatedGroups() {
        if (relatedGroupsBuffer.length > 0) {
            // S'il y a plusieurs groupes consecutifs, les marquer comme groupes lies
            if (relatedGroupsBuffer.length > 1) {
                relatedGroupsBuffer.forEach((group, idx) => {
                    group.isRelatedGroup = true;
                    group.relatedGroupIndex = idx;
                    group.relatedGroupTotal = relatedGroupsBuffer.length;
                });
            }
            result.wordGroups.push(...relatedGroupsBuffer);
            relatedGroupsBuffer = [];
        }
    }

    for (let i = 0; i < lines.length; i++) {
        const line = lines[i];
        const trimmed = line.trim();

        // Collecte les lignes de commentaire (dans la zone [WORD_GROUPS])
        if (trimmed.startsWith('#') && currentSection === 'groups') {
            pendingComments.push(line);
            continue;
        }

        // Ignore les commentaires (hors zone [WORD_GROUPS])
        if (trimmed.startsWith('#')) continue;

        // Ligne vide : termine le groupe courant et le cache des groupes lies
        if (!trimmed) {
            if (currentGroup) {
                // Enregistre le groupe courant dans le cache
                relatedGroupsBuffer.push(currentGroup);
                currentGroup = null;
            }
            // Une ligne vide marque la fin des groupes lies, on vide le cache
            flushRelatedGroups();
            lastLineWasAlias = false;
            // Dans la zone [WORD_GROUPS], une ligne vide rejoint les commentaires a attribuer (preserve la structure des lignes vides)
            if (currentSection === 'groups') {
                pendingComments.push('');
            }
            continue;
        }

        // Detecte les marqueurs de zone
        if (trimmed === '[GLOBAL_FILTER]') {
            currentSection = 'global';
            continue;
        }
        if (trimmed === '[WORD_GROUPS]') {
            currentSection = 'groups';
            continue;
        }

        // Traite le contenu
        if (currentSection === 'global') {
            result.globalFilter.push(trimmed);
        } else if (currentSection === 'groups') {
            // Detecte l'alias de groupe [nom du groupe]
            const groupNameMatch = trimmed.match(/^\[([^\]]+)\]$/);
            if (groupNameMatch && !['GLOBAL_FILTER', 'WORD_GROUPS'].includes(groupNameMatch[1])) {
                // Enregistre le groupe courant dans le cache
                if (currentGroup) {
                    relatedGroupsBuffer.push(currentGroup);
                }
                // Vide le cache (l'alias de groupe forme un groupe a part)
                flushRelatedGroups();
                // Cree un type d'alias de groupe
                currentGroup = {
                    type: 'group-name',
                    name: groupNameMatch[1],
                    keywords: [],
                    startLine: i,
                    precedingComments: pendingComments.length > 0 ? [...pendingComments] : []
                };
                pendingComments = [];
                lastLineWasAlias = false;
            } else {
                // Detecte la syntaxe d'alias => (cote droit autorise vide)
                const aliasMatch = trimmed.match(/^(.+?)\s*=>\s*(.*)$/);
                if (aliasMatch) {
                    const keyword = aliasMatch[1].trim();
                    const alias = aliasMatch[2].trim();

                    // Logique cle : si la ligne precedente etait aussi une ligne d'alias (sans ligne vide), on l'integre au groupe d'alias consecutifs
                    if (lastLineWasAlias && currentGroup && (currentGroup.type === 'alias' || currentGroup.type === 'alias-group')) {
                        // Si l'element courant est un alias unique, on le promeut en groupe d'alias
                        if (currentGroup.type === 'alias') {
                            currentGroup.type = 'alias-group';
                        }
                        // Ajoute au groupe d'alias
                        currentGroup.items.push({ keyword, alias });
                    } else {
                        // Nouvel alias unique (susceptible d'etre promu en groupe d'alias)
                        if (currentGroup) {
                            // Enregistre le groupe courant dans le cache (au lieu de l'ajouter directement au resultat)
                            relatedGroupsBuffer.push(currentGroup);
                        }
                        currentGroup = {
                            type: 'alias',
                            items: [{ keyword, alias }],
                            startLine: i,
                            precedingComments: pendingComments.length > 0 ? [...pendingComments] : []
                        };
                        pendingComments = [];
                    }
                    lastLineWasAlias = true;
                } else {
                    // Mot-cle ordinaire
                    if (!currentGroup || currentGroup.type === 'alias' || currentGroup.type === 'alias-group') {
                        // Si l'element courant est de type alias, on l'enregistre d'abord dans le cache
                        if (currentGroup) {
                            relatedGroupsBuffer.push(currentGroup);
                        }
                        // Cree un nouveau groupe simple
                        currentGroup = {
                            type: 'plain',
                            keywords: [],
                            startLine: i,
                            precedingComments: pendingComments.length > 0 ? [...pendingComments] : []
                        };
                        pendingComments = [];
                    }
                    currentGroup.keywords.push(trimmed);
                    lastLineWasAlias = false;
                }
            }
        }
    }

    // Ajoute le dernier groupe
    if (currentGroup) {
        relatedGroupsBuffer.push(currentGroup);
    }
    flushRelatedGroups();

    return result;
}

function buildFrequencyText(data) {
    // S'il y a un texte d'origine, on tente de preserver les commentaires
    if (data.originalText) {
        const lines = data.originalText.split('\n');
        let result = [];

        // Etape 1 : preserver les commentaires d'en-tete du fichier
        let i = 0;
        while (i < lines.length) {
            const line = lines[i];
            const trimmed = line.trim();

            if (trimmed === '[GLOBAL_FILTER]') {
                break;
            }
            result.push(line);
            i++;
        }

        // Etape 2 : reconstruire la zone [GLOBAL_FILTER]
        result.push('[GLOBAL_FILTER]');

        // Preserve les commentaires apres [GLOBAL_FILTER] (jusqu'a la premiere ligne non commentee et non vide)
        i++;
        while (i < lines.length) {
            const line = lines[i];
            const trimmed = line.trim();
            if (trimmed.startsWith('#') || trimmed === '') {
                result.push(line);
                i++;
            } else {
                break;
            }
        }

        // Ajoute les mots de filtrage global
        data.globalFilter.forEach(filter => {
            result.push(filter);
        });

        // Ignore le contenu [GLOBAL_FILTER] du fichier d'origine (lignes non commentees), preserve lignes vides et commentaires jusqu'a [WORD_GROUPS]
        while (i < lines.length) {
            const line = lines[i];
            const trimmed = line.trim();
            if (trimmed === '[WORD_GROUPS]') {
                break;
            }
            // Preserve commentaires et lignes vides
            if (trimmed.startsWith('#') || trimmed === '') {
                result.push(line);
            }
            i++;
        }

        // Etape 3 : reconstruire la zone [WORD_GROUPS]
        result.push('[WORD_GROUPS]');

        // Ajoute les groupes de mots (les commentaires sont conserves dans precedingComments de chaque groupe)
        data.wordGroups.forEach((group, index) => {
            // Affiche d'abord les commentaires precedant le groupe
            if (group.precedingComments && group.precedingComments.length > 0) {
                group.precedingComments.forEach(comment => {
                    result.push(comment);
                });
            }

            if (group.type === 'group-name') {
                // Type alias de groupe : [nom du groupe] + mots-cles
                if (group.name) {
                    result.push(`[${group.name}]`);
                }
                group.keywords.forEach(kw => {
                    result.push(kw);
                });
            } else if (group.type === 'alias' || group.type === 'alias-group') {
                // Type alias : keyword => alias
                group.items.forEach(item => {
                    result.push(`${item.keyword} => ${item.alias}`);
                });
            } else if (group.type === 'plain') {
                // Groupe simple
                group.keywords.forEach(kw => {
                    result.push(kw);
                });
            }

            // Logique de gestion des lignes vides :
            // 1. Si le groupe courant et le suivant sont tous deux lies, ne pas ajouter de ligne vide
            // 2. Sinon, ajouter une ligne vide entre les groupes
            const isLastGroup = index === data.wordGroups.length - 1;
            const nextGroup = !isLastGroup ? data.wordGroups[index + 1] : null;

            // Test simplifie : tant que le courant et le suivant sont lies, ne pas ajouter de ligne vide
            const bothAreRelatedGroups = group.isRelatedGroup && nextGroup && nextGroup.isRelatedGroup;

            // Si le groupe suivant a des commentaires en amont, pas besoin d'ajouter de ligne vide (deja incluse dans les commentaires)
            const nextHasComments = nextGroup && nextGroup.precedingComments && nextGroup.precedingComments.length > 0;

            if (bothAreRelatedGroups) {
                // Pas de ligne vide a l'interieur des groupes lies
                // N'ajoute rien
            } else if (!isLastGroup && !nextHasComments) {
                // Ajoute une ligne vide entre les groupes (si le suivant n'a pas de commentaire en amont)
                result.push('');
            } else if (isLastGroup) {
                // Conserve aussi une ligne vide apres le dernier groupe
                result.push('');
            }
        });

        return result.join('\n');
    }

    // S'il n'y a pas de texte d'origine, utilise le modele par defaut
    let text = '# ═══════════════════════════════════════════════════════════════\n';
    text += '#                    Fichier de configuration des mots de frequence TrendRadar\n';
    text += '# ═══════════════════════════════════════════════════════════════\n\n';

    text += '[GLOBAL_FILTER]\n';
    data.globalFilter.forEach(filter => {
        text += filter + '\n';
    });
    text += '\n\n';

    text += '[WORD_GROUPS]\n\n';
    data.wordGroups.forEach((group, index) => {
        // Affiche d'abord les commentaires precedant le groupe
        if (group.precedingComments && group.precedingComments.length > 0) {
            group.precedingComments.forEach(comment => {
                text += comment + '\n';
            });
        }

        if (group.type === 'group-name') {
            if (group.name) {
                text += `[${group.name}]\n`;
            }
            group.keywords.forEach(kw => {
                text += kw + '\n';
            });
        } else if (group.type === 'alias' || group.type === 'alias-group') {
            group.items.forEach(item => {
                text += `${item.keyword} => ${item.alias}\n`;
            });
        } else if (group.type === 'plain') {
            group.keywords.forEach(kw => {
                text += kw + '\n';
            });
        }

        // Logique de gestion des lignes vides : identique a ci-dessus
        const isLastGroup = index === data.wordGroups.length - 1;
        const nextGroup = !isLastGroup ? data.wordGroups[index + 1] : null;

        const bothAreRelatedGroups = group.isRelatedGroup && nextGroup && nextGroup.isRelatedGroup;

        // Si le groupe suivant a des commentaires en amont, pas besoin d'ajouter de ligne vide
        const nextHasComments = nextGroup && nextGroup.precedingComments && nextGroup.precedingComments.length > 0;

        if (bothAreRelatedGroups) {
            // Pas de ligne vide a l'interieur des groupes lies
        } else if (!isLastGroup && !nextHasComments) {
            text += '\n';  // Separe les groupes par une ligne vide
        } else if (isLastGroup) {
            text += '\n';  // Conserve aussi une ligne vide apres le dernier groupe
        }
    });

    return text;
}

function syncFrequencyToUI() {
    const data = parseFrequencyText(currentFrequency);
    currentFrequencyData = data;
    renderFrequencyPanel(data);
}

function renderFrequencyPanel(data) {
    if (!data) {
        data = parseFrequencyText(currentFrequency);
    }

    const panel = document.getElementById('frequency-panel');

    // Fonction utilitaire : renvoie la classe de style selon le type de mot-cle
    function getKeywordClass(keyword) {
        if (keyword.startsWith('+')) return 'bg-green-500';
        if (keyword.startsWith('!')) return 'bg-red-500';
        if (keyword.startsWith('@')) return 'bg-purple-500';
        if (keyword.startsWith('/') || keyword.includes('=>')) return 'bg-indigo-500';
        return 'bg-blue-500';
    }

    // Fonction utilitaire : ajoute une etiquette au mot-cle
    function getKeywordLabel(keyword) {
        if (keyword.startsWith('+')) return 'Obligatoire';
        if (keyword.startsWith('!')) return 'Exclure';
        if (keyword.startsWith('@')) return 'Restreindre';
        if (keyword.startsWith('/')) return 'Regex';
        if (keyword.includes('=>')) return 'Alias';
        return '';
    }

    // Affiche la carte du groupe de mots
    function renderGroupCard(group, idx) {
        const jumpIcon = `<i class="fa-solid fa-grip-vertical text-gray-400 text-xs mr-2" title="Glissez pour reordonner"></i>`;

        // Marqueur de numero d'ordre
        const indexBadge = `<span class="text-xs bg-gray-700 text-white px-2.5 py-1 rounded-full font-bold mr-2" title="Numero d'ordre du groupe">#${idx + 1}</span>`;

        // Marqueur de groupe lie
        const relatedGroupBadge = group.isRelatedGroup
            ? `<span class="text-[10px] bg-gradient-to-r from-blue-500 to-indigo-500 text-white px-2 py-0.5 rounded font-bold ml-2" title="Ce groupe est lie au groupe adjacent (sans ligne vide separatrice)">
                <i class="fa-solid fa-link mr-1"></i>Groupe lie ${group.relatedGroupIndex + 1}/${group.relatedGroupTotal}
               </span>`
            : '';

        // Style de bordure du groupe lie
        const relatedGroupStyle = group.isRelatedGroup
            ? 'border-l-4 border-l-blue-500 shadow-lg'
            : '';

        if (group.type === 'group-name') {
            // Type alias de groupe
            return `
                <div class="word-group-card border-2 border-orange-200 bg-orange-50 group ${relatedGroupStyle} cursor-move" data-group-index="${idx}" onclick="scrollToWordGroupInEditor(${idx})">
                    <div class="flex items-center justify-between mb-3">
                        <div class="flex items-center flex-1 gap-2">
                            ${jumpIcon}
                            ${indexBadge}
                            <span class="text-[10px] bg-orange-500 text-white px-2 py-0.5 rounded font-bold">Alias de groupe</span>
                            ${relatedGroupBadge}
                            <input type="text" value="${group.name || ''}" placeholder="Alias de groupe (ex. : Asie de l'Est)"
                                   class="text-sm font-bold border-0 border-b-2 border-orange-300 focus:border-orange-500 outline-none px-2 py-1 flex-1 bg-transparent"
                                   onclick="event.stopPropagation()"
                                   onchange="updateGroupName(${idx}, this.value)">
                        </div>
                        <button onclick="event.stopPropagation(); removeWordGroup(${idx})" class="text-red-500 hover:text-red-700 text-xs ml-2">
                            <i class="fa-solid fa-trash"></i>
                        </button>
                    </div>
                    <div class="bg-white rounded p-3 border border-orange-200 editable-area" onclick="event.stopPropagation()">
                        <div class="text-xs text-gray-600 mb-2 font-bold">Liste des mots-cles :</div>
                        <div class="tag-input-container">
                            ${group.keywords.map(kw => {
                                const label = getKeywordLabel(kw);
                                const escapedKw = kw.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
                                return `
                                    <span class="tag-item ${getKeywordClass(kw)} relative break-all cursor-pointer" data-keyword="${escapedKw}" onclick="editKeyword(${idx}, this.dataset.keyword, this)">
                                        ${label ? `<span class="text-[9px] opacity-75 mr-1">[${label}]</span>` : ''}
                                        ${escapedKw}
                                        <button data-keyword="${escapedKw}" onclick="event.stopPropagation(); removeKeyword(${idx}, this.dataset.keyword)">×</button>
                                    </span>
                                `;
                            }).join('')}
                            <input type="text" class="tag-input" placeholder="Saisissez un mot-cle puis appuyez sur Entree..."
                                   onkeydown="handleKeywordInput(event, ${idx})">
                        </div>
                        <div class="flex items-center justify-between mt-2">
                            <button onclick="openDeepSeekAI('group', ${idx})" class="text-xs text-blue-600 hover:text-blue-700 flex items-center gap-1">
                                <i class="fa-solid fa-wand-magic-sparkles"></i>Generer une regex par IA
                            </button>
                            <div class="text-[10px] text-gray-400">${group.keywords.length} mot(s)-cle(s)</div>
                        </div>
                    </div>
                </div>
            `;
        } else if (group.type === 'alias') {
            // Type alias unique
            const item = group.items[0];
            return `
                <div class="word-group-card border-2 border-teal-200 bg-teal-50 group ${relatedGroupStyle} cursor-move" data-group-index="${idx}" onclick="scrollToWordGroupInEditor(${idx})">
                    <div class="flex items-center justify-between mb-3">
                        <div class="flex items-center flex-1 gap-2">
                            ${jumpIcon}
                            ${indexBadge}
                            <span class="text-[10px] bg-teal-500 text-white px-2 py-0.5 rounded font-bold">Alias unique</span>
                            ${relatedGroupBadge}
                        </div>
                        <button onclick="event.stopPropagation(); removeWordGroup(${idx})" class="text-red-500 hover:text-red-700 text-xs">
                            <i class="fa-solid fa-trash"></i>
                        </button>
                    </div>
                    <div class="bg-white rounded p-3 border border-teal-200 editable-area" onclick="event.stopPropagation()">
                        <div class="flex items-center gap-2">
                            <input type="text" value="${item.keyword || ''}" placeholder="/regex/ ou mot-cle"
                                   class="flex-1 px-3 py-2 border border-gray-300 rounded focus:border-teal-500 outline-none text-sm font-mono"
                                   onblur="updateAliasItem(${idx}, 0, 'keyword', this.value)">
                            <span class="text-teal-600 font-bold">=></span>
                            <input type="text" value="${item.alias || ''}" placeholder="Alias"
                                   class="flex-1 px-3 py-2 border border-gray-300 rounded focus:border-teal-500 outline-none text-sm"
                                   onblur="updateAliasItem(${idx}, 0, 'alias', this.value)">
                        </div>
                        <div class="flex items-center justify-between mt-2">
                            <button onclick="openDeepSeekAI('group', ${idx})" class="text-xs text-blue-600 hover:text-blue-700 flex items-center gap-1">
                                <i class="fa-solid fa-wand-magic-sparkles"></i>Generer une regex par IA
                            </button>
                            <div class="text-[10px] text-gray-500">
                                <i class="fa-solid fa-lightbulb mr-1"></i>Exemple : /Pangdonglai|Yu Donglai/ => Pangdonglai
                            </div>
                        </div>
                    </div>
                </div>
            `;
        } else if (group.type === 'alias-group') {
            // Type groupe d'alias consecutifs
            return `
                <div class="word-group-card border-2 border-purple-200 bg-purple-50 group ${relatedGroupStyle} cursor-move" data-group-index="${idx}" onclick="scrollToWordGroupInEditor(${idx})">
                    <div class="flex items-center justify-between mb-3">
                        <div class="flex items-center flex-1 gap-2">
                            ${jumpIcon}
                            ${indexBadge}
                            <span class="text-[10px] bg-purple-500 text-white px-2 py-0.5 rounded font-bold">Groupe d'alias consecutifs</span>
                            ${relatedGroupBadge}
                        </div>
                        <button onclick="event.stopPropagation(); removeWordGroup(${idx})" class="text-red-500 hover:text-red-700 text-xs">
                            <i class="fa-solid fa-trash"></i>
                        </button>
                    </div>
                    <div class="bg-white rounded p-3 border border-purple-200 space-y-2 editable-area" onclick="event.stopPropagation()">
                        <div class="text-xs text-gray-600 mb-2 font-bold">
                            Liste des alias (sans ligne vide separatrice) :
                        </div>
                        ${group.items.map((item, itemIdx) => `
                            <div class="flex items-center gap-2">
                                <input type="text" value="${item.keyword || ''}" placeholder="/regex/ ou mot-cle"
                                       class="flex-1 px-3 py-2 border border-gray-300 rounded focus:border-purple-500 outline-none text-sm font-mono"
                                       onblur="updateAliasItem(${idx}, ${itemIdx}, 'keyword', this.value)">
                                <span class="text-purple-600 font-bold">=></span>
                                <input type="text" value="${item.alias || ''}" placeholder="Alias"
                                       class="flex-1 px-3 py-2 border border-gray-300 rounded focus:border-purple-500 outline-none text-sm"
                                       onblur="updateAliasItem(${idx}, ${itemIdx}, 'alias', this.value)">
                                <button onclick="removeAliasItem(${idx}, ${itemIdx})" class="text-red-500 hover:text-red-700 text-xs">
                                    <i class="fa-solid fa-trash"></i>
                                </button>
                            </div>
                        `).join('')}
                        <div class="flex items-center justify-between mt-2">
                            <button onclick="openDeepSeekAI('group', ${idx})" class="text-xs text-blue-600 hover:text-blue-700 flex items-center gap-1">
                                <i class="fa-solid fa-wand-magic-sparkles"></i>Generer une regex par IA
                            </button>
                            <div class="text-[10px] text-gray-500">
                                <i class="fa-solid fa-info-circle mr-1"></i>Ces lignes d'alias ne sont pas separees par des lignes vides dans le fichier et appartiennent au meme groupe
                            </div>
                        </div>
                    </div>
                </div>
            `;
        } else if (group.type === 'plain') {
            // Type groupe simple
            return `
                <div class="word-group-card border-2 border-gray-200 bg-gray-50 group ${relatedGroupStyle} cursor-move" data-group-index="${idx}" onclick="scrollToWordGroupInEditor(${idx})">
                    <div class="flex items-center justify-between mb-3">
                        <div class="flex items-center flex-1 gap-2">
                            ${jumpIcon}
                            ${indexBadge}
                            <span class="text-[10px] bg-gray-500 text-white px-2 py-0.5 rounded font-bold">Groupe simple</span>
                            ${relatedGroupBadge}
                        </div>
                        <button onclick="event.stopPropagation(); removeWordGroup(${idx})" class="text-red-500 hover:text-red-700 text-xs">
                            <i class="fa-solid fa-trash"></i>
                        </button>
                    </div>
                    <div class="bg-white rounded p-3 border border-gray-200 editable-area" onclick="event.stopPropagation()">
                        <div class="tag-input-container">
                            ${group.keywords.map(kw => {
                                const label = getKeywordLabel(kw);
                                const escapedKw = kw.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
                                return `
                                    <span class="tag-item ${getKeywordClass(kw)} relative break-all cursor-pointer" data-keyword="${escapedKw}" onclick="editKeyword(${idx}, this.dataset.keyword, this)">
                                        ${label ? `<span class="text-[9px] opacity-75 mr-1">[${label}]</span>` : ''}
                                        ${escapedKw}
                                        <button data-keyword="${escapedKw}" onclick="event.stopPropagation(); removeKeyword(${idx}, this.dataset.keyword)">×</button>
                                    </span>
                                `;
                            }).join('')}
                            <input type="text" class="tag-input" placeholder="Saisissez un mot-cle puis appuyez sur Entree..."
                                   onkeydown="handleKeywordInput(event, ${idx})">
                        </div>
                        <div class="flex items-center justify-between mt-2">
                            <button onclick="openDeepSeekAI('group', ${idx})" class="text-xs text-blue-600 hover:text-blue-700 flex items-center gap-1">
                                <i class="fa-solid fa-wand-magic-sparkles"></i>Generer une regex par IA
                            </button>
                            <div class="text-[10px] text-gray-400">${group.keywords.length} mot(s)-cle(s)</div>
                        </div>
                    </div>
                </div>
            `;
        }
        return '';
    }

    panel.innerHTML = `
        <!-- Zone d'explication des regles -->
        <div class="bg-gradient-to-r from-blue-50 to-indigo-50 rounded-lg border border-blue-200 p-4 mb-4">
            <div class="flex items-start gap-3">
                <i class="fa-solid fa-book text-blue-600 text-lg mt-0.5"></i>
                <div class="flex-1">
                    <h3 class="text-sm font-bold text-gray-800 mb-2">Description des quatre types de groupes de mots</h3>
                    <div class="grid grid-cols-2 gap-3 text-xs">
                        <div class="bg-white rounded p-2 border-l-4 border-orange-500">
                            <div class="font-bold text-orange-700 mb-1">Alias de groupe</div>
                            <div class="text-gray-600 font-mono text-[10px] mb-1">[Asie de l'Est]<br>Japon<br>Coree</div>
                            <div class="text-gray-500 text-[10px]">Plusieurs mots-cles, affiches sous un nom de groupe unique</div>
                        </div>
                        <div class="bg-white rounded p-2 border-l-4 border-teal-500">
                            <div class="font-bold text-teal-700 mb-1">Alias unique</div>
                            <div class="text-gray-600 font-mono text-[10px] mb-1">/Pangdonglai|Yu Donglai/ => Pangdonglai</div>
                            <div class="text-gray-500 text-[10px]">Correspondance par regex, affichee en alias</div>
                        </div>
                        <div class="bg-white rounded p-2 border-l-4 border-purple-500">
                            <div class="font-bold text-purple-700 mb-1">Groupe d'alias consecutifs</div>
                            <div class="text-gray-600 font-mono text-[10px] mb-1">/Zhiyuan|Zhihuijun/ => Zhiyuan<br>/Zhongqing|EngineAI/ => Zhongqing</div>
                            <div class="text-gray-500 text-[10px]">Plusieurs alias sans ligne vide separatrice</div>
                        </div>
                        <div class="bg-white rounded p-2 border-l-4 border-gray-500">
                            <div class="font-bold text-gray-700 mb-1">Groupe simple</div>
                            <div class="text-gray-600 font-mono text-[10px] mb-1">Candidature olympique</div>
                            <div class="text-gray-500 text-[10px]">Mot-cle ordinaire</div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Zone du filtre global -->
        <div class="bg-white rounded-lg border border-gray-200 p-5">
            <div class="flex items-center justify-between mb-3">
                <h3 class="text-sm font-bold text-gray-700">
                    <i class="fa-solid fa-filter mr-2"></i>Mots de filtrage global
                </h3>
                <button onclick="openDeepSeekAI('global')" class="text-xs text-blue-600 hover:text-blue-700 flex items-center gap-1">
                    <i class="fa-solid fa-wand-magic-sparkles"></i>Generer une regex par IA
                </button>
            </div>
            <div id="global-filter-tags" class="tag-input-container">
                ${data.globalFilter.map(f => `
                    <span class="tag-item ${getKeywordClass(f)}">
                        ${f}
                        <button onclick="removeGlobalFilter('${f.replace(/'/g, "\\'")}')">×</button>
                    </span>
                `).join('')}
                <input type="text" class="tag-input" placeholder="Saisissez un mot de filtrage puis appuyez sur Entree..." onkeydown="handleGlobalFilterInput(event)">
            </div>
            <div class="text-xs text-gray-500 mt-2">
                <i class="fa-solid fa-lightbulb mr-1"></i>Astuce : les expressions regulieres sont acceptees (entourees de /.../) 
            </div>
        </div>

        <!-- Zone des groupes de mots -->
        <div class="bg-white rounded-lg border border-gray-200 p-5">
            <div class="flex items-center justify-between mb-3">
                <h3 class="text-sm font-bold text-gray-700">
                    <i class="fa-solid fa-layer-group mr-2"></i>Groupes de mots-cles <span class="text-xs text-gray-400 font-normal">(${data.wordGroups.length} groupe(s))</span>
                </h3>
                <button onclick="addWordGroup('top')" class="text-xs bg-blue-600 text-white px-3 py-1 rounded hover:bg-blue-700">
                    <i class="fa-solid fa-plus mr-1"></i>Ajouter un groupe
                </button>
            </div>
            <div id="word-groups-container" class="space-y-3">
                ${data.wordGroups.map((group, idx) => {
                    const card = renderGroupCard(group, idx);
                    // Ajoute une zone d'insertion apres chaque groupe (sauf le dernier)
                    if (idx < data.wordGroups.length - 1) {
                        return card + `
                            <div class="insert-zone group/insert" data-insert-index="${idx + 1}">
                                <button onclick="insertWordGroupAt(${idx + 1})" class="insert-button">
                                    <i class="fa-solid fa-plus"></i>
                                </button>
                            </div>
                        `;
                    }
                    return card;
                }).join('')}
            </div>

            <!-- Bouton d'ajout en bas -->
            <div class="mt-4 flex justify-center">
                <button onclick="addWordGroup('bottom')" class="text-sm bg-gradient-to-r from-blue-500 to-blue-600 text-white px-6 py-2 rounded-lg hover:from-blue-600 hover:to-blue-700 shadow-sm transition-all flex items-center gap-2">
                    <i class="fa-solid fa-plus-circle"></i>
                    <span>Ajouter un groupe en bas</span>
                </button>
            </div>
        </div>
    `;

    // Initialise la fonction de tri par glisser-deposer
    setTimeout(() => {
        const container = document.getElementById('word-groups-container');
        if (container && typeof Sortable !== 'undefined') {
            // Detruit l'instance precedente (si elle existe)
            if (container.sortableInstance) {
                container.sortableInstance.destroy();
            }

            // Cree une nouvelle instance Sortable
            container.sortableInstance = new Sortable(container, {
                animation: 150,
                filter: '.editable-area, input, button, select, textarea',  // Exclut la zone d'edition
                preventOnFilter: false,  // Autorise l'interaction normale dans la zone filtree
                ghostClass: 'sortable-ghost',
                chosenClass: 'sortable-chosen',
                dragClass: 'sortable-drag',
                onEnd: function(evt) {
                    // Recupere l'ordre actuel de toutes les cartes de groupe
                    const cards = Array.from(container.querySelectorAll('.word-group-card'));
                    const newOrder = cards.map(card => parseInt(card.getAttribute('data-group-index')));

                    // Verifie si l'ordre a change
                    const data = currentFrequencyData || parseFrequencyText(currentFrequency);
                    const oldOrder = data.wordGroups.map((_, idx) => idx);

                    if (JSON.stringify(newOrder) !== JSON.stringify(oldOrder)) {
                        // Reorganise les donnees selon le nouvel ordre
                        const reorderedGroups = newOrder.map(idx => data.wordGroups[idx]);
                        data.wordGroups = reorderedGroups;

                        // Reconstruit le texte
                        currentFrequency = buildFrequencyText(data);
                        currentFrequencyData = parseFrequencyText(currentFrequency);
                        document.getElementById('frequency-editor').value = currentFrequency;
                        updateBackdrop('frequency-editor', 'frequency-backdrop');

                        // Reaffiche
                        renderFrequencyPanel(currentFrequencyData);
                    }
                }
            });
        }
    }, 0);
}

// Operations sur le filtre global
window.handleGlobalFilterInput = function(event) {
    if (event.key === 'Enter' && event.target.value.trim()) {
        const data = currentFrequencyData || parseFrequencyText(currentFrequency);
        data.globalFilter.push(event.target.value.trim());
        currentFrequency = buildFrequencyText(data);
        currentFrequencyData = data;
        document.getElementById('frequency-editor').value = currentFrequency;
    updateBackdrop('frequency-editor', 'frequency-backdrop');
        renderFrequencyPanel(data);
    }
}

window.removeGlobalFilter = function(filter) {
    const data = currentFrequencyData || parseFrequencyText(currentFrequency);
    data.globalFilter = data.globalFilter.filter(f => f !== filter);
    currentFrequency = buildFrequencyText(data);
    currentFrequencyData = data;
    document.getElementById('frequency-editor').value = currentFrequency;
    updateBackdrop('frequency-editor', 'frequency-backdrop');
    renderFrequencyPanel(data);
}

// Operations sur les groupes de mots
let pendingWordGroupPosition = 'top';  // Memorise la position d'ajout : 'top', 'bottom' ou un index numerique

window.addWordGroup = function(position = 'top') {
    pendingWordGroupPosition = position;
    document.getElementById('wordgroup-type-modal').classList.remove('hidden');
}

// Insere un groupe a la position indiquee
window.insertWordGroupAt = function(index) {
    pendingWordGroupPosition = index;  // Memorise la position d'insertion (index numerique)
    document.getElementById('wordgroup-type-modal').classList.remove('hidden');
}

window.closeWordGroupTypeModal = function() {
    document.getElementById('wordgroup-type-modal').classList.add('hidden');
}

window.confirmAddWordGroup = function(type) {
    const data = currentFrequencyData || parseFrequencyText(currentFrequency);
    let newGroup;

    if (type === 'group') {
        // Type alias de groupe
        newGroup = { type: 'group-name', name: '', keywords: [] };
    } else if (type === 'alias') {
        // Type alias unique
        newGroup = { type: 'alias', items: [{ keyword: '', alias: '' }] };
    } else if (type === 'multi-alias') {
        // Type alias consecutifs (plusieurs lignes d'alias)
        newGroup = { type: 'alias-group', items: [{ keyword: '', alias: '' }, { keyword: '', alias: '' }] };
    } else if (type === 'plain') {
        // Type groupe simple
        newGroup = { type: 'plain', keywords: [] };
    }

    // Insere selon la position
    if (pendingWordGroupPosition === 'bottom') {
        data.wordGroups.push(newGroup);
    } else if (pendingWordGroupPosition === 'top') {
        data.wordGroups.unshift(newGroup);
    } else if (typeof pendingWordGroupPosition === 'number') {
        // Insere a l'index indique
        data.wordGroups.splice(pendingWordGroupPosition, 0, newGroup);
    }

    currentFrequency = buildFrequencyText(data);
    currentFrequencyData = data;
    document.getElementById('frequency-editor').value = currentFrequency;
    updateBackdrop('frequency-editor', 'frequency-backdrop');
    renderFrequencyPanel(data);

    closeWordGroupTypeModal();

    // Defile jusqu'au groupe nouvellement ajoute
    setTimeout(() => {
        const container = document.getElementById('word-groups-container');
        if (pendingWordGroupPosition === 'bottom') {
            container.scrollTop = container.scrollHeight;
        } else if (pendingWordGroupPosition === 'top') {
            container.scrollTop = 0;
        } else if (typeof pendingWordGroupPosition === 'number') {
            // Defile jusqu'a la position d'insertion
            const cards = container.querySelectorAll('.word-group-card');
            if (cards[pendingWordGroupPosition]) {
                cards[pendingWordGroupPosition].scrollIntoView({ behavior: 'smooth', block: 'center' });
            }
        }
    }, 100);
}

window.removeWordGroup = function(index) {
    const data = currentFrequencyData || parseFrequencyText(currentFrequency);
    data.wordGroups.splice(index, 1);
    currentFrequency = buildFrequencyText(data);
    // Reanalyse pour mettre a jour les informations de groupes lies
    currentFrequencyData = parseFrequencyText(currentFrequency);
    document.getElementById('frequency-editor').value = currentFrequency;
    updateBackdrop('frequency-editor', 'frequency-backdrop');
    renderFrequencyPanel(currentFrequencyData);
}

window.updateGroupName = function(index, name) {
    const data = currentFrequencyData || parseFrequencyText(currentFrequency);
    const group = data.wordGroups[index];

    // Seul le type group-name possede un champ name
    if (group.type === 'group-name') {
        group.name = name;
    }

    currentFrequency = buildFrequencyText(data);
    // Reanalyse pour mettre a jour les informations de groupes lies
    currentFrequencyData = parseFrequencyText(currentFrequency);
    document.getElementById('frequency-editor').value = currentFrequency;
    updateBackdrop('frequency-editor', 'frequency-backdrop');
    renderFrequencyPanel(currentFrequencyData);
}

window.editKeyword = function(groupIndex, oldKeyword, spanElement) {
    const data = currentFrequencyData || parseFrequencyText(currentFrequency);
    const group = data.wordGroups[groupIndex];

    // Seuls les types group-name et plain possedent un champ keywords
    if (group.type !== 'group-name' && group.type !== 'plain') {
        return;
    }

    const originalKeyword = group.keywords.find(kw => kw === oldKeyword) || oldKeyword;

    const input = document.createElement('input');
    input.type = 'text';
    input.value = originalKeyword;
    input.className = 'tag-input inline-block px-2 py-1 text-xs border border-blue-500 rounded';
    input.style.minWidth = '100px';

    const saveEdit = () => {
        const newKeyword = input.value.trim();
        if (newKeyword && newKeyword !== originalKeyword) {
            const kwIndex = group.keywords.indexOf(originalKeyword);
            if (kwIndex !== -1) {
                group.keywords[kwIndex] = newKeyword;
            }
            currentFrequency = buildFrequencyText(data);
            // Reanalyse pour mettre a jour les informations de groupes lies
            currentFrequencyData = parseFrequencyText(currentFrequency);
            document.getElementById('frequency-editor').value = currentFrequency;
    updateBackdrop('frequency-editor', 'frequency-backdrop');
            renderFrequencyPanel(currentFrequencyData);
        } else {
            spanElement.style.display = '';
            input.remove();
        }
    };

    input.onblur = saveEdit;
    input.onkeydown = (e) => {
        if (e.key === 'Enter') {
            saveEdit();
        } else if (e.key === 'Escape') {
            spanElement.style.display = '';
            input.remove();
        }
    };

    spanElement.style.display = 'none';
    spanElement.parentNode.insertBefore(input, spanElement);
    input.focus();
    input.select();
}

window.handleKeywordInput = function(event, groupIndex) {
    if (event.key === 'Enter' && event.target.value.trim()) {
        const data = currentFrequencyData || parseFrequencyText(currentFrequency);
        const group = data.wordGroups[groupIndex];

        // Seuls les types group-name et plain peuvent recevoir des mots-cles
        if (group.type === 'group-name' || group.type === 'plain') {
            group.keywords.push(event.target.value.trim());
            event.target.value = '';

            currentFrequency = buildFrequencyText(data);
            // Reanalyse pour mettre a jour les informations de groupes lies
            currentFrequencyData = parseFrequencyText(currentFrequency);
            document.getElementById('frequency-editor').value = currentFrequency;
    updateBackdrop('frequency-editor', 'frequency-backdrop');
            renderFrequencyPanel(currentFrequencyData);
        }
    }
}

window.removeKeyword = function(groupIndex, keyword) {
    const data = currentFrequencyData || parseFrequencyText(currentFrequency);
    const group = data.wordGroups[groupIndex];

    // Seuls les types group-name et plain peuvent supprimer des mots-cles
    if (group.type === 'group-name' || group.type === 'plain') {
        group.keywords = group.keywords.filter(k => k !== keyword);

        // Si le groupe devient vide, supprime le groupe entier
        if (group.keywords.length === 0) {
            data.wordGroups.splice(groupIndex, 1);
        }

        currentFrequency = buildFrequencyText(data);
        // Reanalyse pour mettre a jour les informations de groupes lies
        currentFrequencyData = parseFrequencyText(currentFrequency);
        document.getElementById('frequency-editor').value = currentFrequency;
    updateBackdrop('frequency-editor', 'frequency-backdrop');
        renderFrequencyPanel(currentFrequencyData);
    }
}

// Met a jour l'element d'alias
window.updateAliasItem = function(groupIndex, itemIndex, field, value) {
    const data = currentFrequencyData || parseFrequencyText(currentFrequency);
    const group = data.wordGroups[groupIndex];

    // Seuls les types alias et alias-group possedent un champ items
    if (group.type === 'alias' || group.type === 'alias-group') {
        if (group.items[itemIndex]) {
            group.items[itemIndex][field] = value;

            currentFrequency = buildFrequencyText(data);
            currentFrequencyData = parseFrequencyText(currentFrequency);
            document.getElementById('frequency-editor').value = currentFrequency;
            updateBackdrop('frequency-editor', 'frequency-backdrop');
            renderFrequencyPanel(currentFrequencyData);
        }
    }
}

// Ajoute un element d'alias
window.addAliasItem = function(groupIndex) {
    const data = currentFrequencyData || parseFrequencyText(currentFrequency);
    const group = data.wordGroups[groupIndex];

    // Seul le type alias-group peut recevoir des elements d'alias
    if (group.type === 'alias-group') {
        group.items.push({ keyword: '', alias: '' });

        currentFrequency = buildFrequencyText(data);
        // Reanalyse pour mettre a jour les informations de groupes lies
        currentFrequencyData = parseFrequencyText(currentFrequency);
        document.getElementById('frequency-editor').value = currentFrequency;
    updateBackdrop('frequency-editor', 'frequency-backdrop');
        renderFrequencyPanel(currentFrequencyData);
    } else if (group.type === 'alias') {
        // Si c'est un alias unique, on le promeut en groupe d'alias
        group.type = 'alias-group';
        group.items.push({ keyword: '', alias: '' });

        currentFrequency = buildFrequencyText(data);
        // Reanalyse pour mettre a jour les informations de groupes lies
        currentFrequencyData = parseFrequencyText(currentFrequency);
        document.getElementById('frequency-editor').value = currentFrequency;
    updateBackdrop('frequency-editor', 'frequency-backdrop');
        renderFrequencyPanel(currentFrequencyData);
    }
}

// Supprime un element d'alias
window.removeAliasItem = function(groupIndex, itemIndex) {
    const data = currentFrequencyData || parseFrequencyText(currentFrequency);
    const group = data.wordGroups[groupIndex];

    // Seul le type alias-group peut supprimer des elements d'alias
    if (group.type === 'alias-group') {
        group.items.splice(itemIndex, 1);

        // S'il ne reste plus d'element d'alias, supprime le groupe entier
        if (group.items.length === 0) {
            data.wordGroups.splice(groupIndex, 1);
        }
        // S'il ne reste qu'un element d'alias, retrograde en alias unique
        else if (group.items.length === 1) {
            group.type = 'alias';
        }

        currentFrequency = buildFrequencyText(data);
        currentFrequencyData = parseFrequencyText(currentFrequency);
        document.getElementById('frequency-editor').value = currentFrequency;
    updateBackdrop('frequency-editor', 'frequency-backdrop');
        renderFrequencyPanel(currentFrequencyData);
    }
}

// Assistant IA DeepSeek
window.openDeepSeekAI = function(type, groupIndex) {
    const userInput = window.prompt('Saisissez le mot-cle principal (ex. : Huawei) :');
    if (!userInput) return;

    const promptText = `Je configure un systeme d'agregation d'actualites et j'ai besoin d'une expression reguliere Python pour collecter des news a propos de [${userInput}].

Aide-moi a suivre les etapes ci-dessous et a ne produire au final qu'une seule chaine d'expression reguliere :

Etape 1 : [Selection precise des mots-cles]
Liste les termes essentiels fortement lies a [${userInput}] :
1. Marques principales : nom complet, abreviation, code boursier, alias.
2. Personnes cles : uniquement les plus hauts dirigeants ou les fondateurs tres representatifs.
3. Produits exclusifs : uniquement des noms de produits exclusifs tres reconnaissables.
4. Studios / sous-marques principaux : entites rattachees fortement liees.

Etape 2 : [Nettoyage et filtrage stricts] (a appliquer rigoureusement)
1. Dedoublonnage par inclusion (principe de la correspondance la plus courte) :
   - Termes courts : si la liste contient deja un terme court essentiel (ex. « Tencent »), supprime tous les termes longs qui le contiennent (ex. « Tencent Cloud », « Tencent Video »), car ils seront deja captures par le terme court.
   - Anglais : si \\bKeyword\\b est present, ne fais pas reapparaitre Keyword.
2. Exclure totalement les entreprises sans rapport :
   - N'inclus jamais : les concurrents ou partenaires de la marque (ex. JD, Meituan, ByteDance et autres societes non affiliees).
3. Exclure totalement le jargon generique :
   - N'inclus jamais : les termes generiques du secteur (ex. « Internet », « grandes entreprises tech », « nouvelles forces productives », « intelligence artificielle », « metavers », « fintech », etc.).

Etape 3 : [Construire la regex Python]
Combine les termes nettoyes en respectant le format suivant :
1. Anglais : tout mot anglais doit etre entoure de \\b (ex. \\bWord\\b) ; aucun mot anglais sans delimiteur de mot n'est autorise.
2. Connecteur : relier avec |.

Format de sortie attendu (exemple) :
/TermeA|TermeB|\\bEnglishWord\\b/ => ${userInput}

Exigences de sortie :
- Uniquement cette ligne d'expression reguliere, sans explication ni bloc de code.`;

    const textArea = document.createElement("textarea");
    textArea.value = promptText;

    textArea.style.position = "fixed";
    textArea.style.left = "-9999px";
    textArea.style.top = "0";
    document.body.appendChild(textArea);

    textArea.focus();
    textArea.select();

    let copySuccess = false;
    try {
        copySuccess = document.execCommand('copy');
    } catch (err) {
        console.error('Echec de la copie :', err);
    }

    document.body.removeChild(textArea);

    if (copySuccess) {
        if (confirm(`Le prompt a ete copie dans le presse-papiers !\n\nMot-cle : ${userInput}\n\nCliquez sur « OK » pour ouvrir le site DeepSeek et collez directement (Ctrl+V).`)) {
            window.open('https://chat.deepseek.com/', '_blank');
        }
    } else {
        prompt('Echec de la copie automatique : copiez manuellement le contenu ci-dessous, puis ouvrez DeepSeek vous-meme :', promptText);
        window.open('https://chat.deepseek.com/', '_blank');
    }
}

// ==========================================
// 10. Fonctions de gestion des plateformes
// ==========================================

// Analyse la liste des plateformes dans la configuration actuelle
function parsePlatformsFromYaml() {
    try {
        const doc = jsyaml.load(currentYaml);
        if (doc && doc.platforms && doc.platforms.sources) {
            return doc.platforms.sources;
        }
    } catch (e) {}
    return [];
}

// Affiche la liste des plateformes
function renderPlatformsList() {
    const container = document.getElementById('platforms-list');
    if (!container) return;

    const platforms = parsePlatformsFromYaml();

    if (platforms.length === 0) {
        container.innerHTML = `<div class="text-xs text-gray-400 italic">Aucune plateforme pour l'instant, veuillez en ajouter</div>`;
        return;
    }

    container.innerHTML = platforms.map((p, idx) => `
        <div class="platform-item flex items-center justify-between bg-gray-50 rounded-lg px-3 py-2 border border-gray-200 hover:border-blue-300 transition-colors" data-index="${idx}">
            <div class="flex items-center gap-2">
                <i class="fa-solid fa-grip-vertical text-gray-300 cursor-move"></i>
                <span class="text-xs font-medium text-gray-700">${p.name}</span>
                <span class="text-[10px] text-gray-400">(${p.id})</span>
            </div>
            <button onclick="removePlatform(${idx})" class="text-red-400 hover:text-red-600 text-xs" title="Supprimer">
                <i class="fa-solid fa-trash"></i>
            </button>
        </div>
    `).join('');

    // Initialise le tri par glisser-deposer
    if (typeof Sortable !== 'undefined') {
        new Sortable(container, {
            animation: 150,
            handle: '.fa-grip-vertical',
            onEnd: function(evt) {
                reorderPlatforms(evt.oldIndex, evt.newIndex);
            }
        });
    }
}

// Supprime une plateforme
window.removePlatform = function(index) {
    const platforms = parsePlatformsFromYaml();
    if (index < 0 || index >= platforms.length) return;

    const platformName = platforms[index].name;
    if (!confirm(`Voulez-vous vraiment supprimer la plateforme "${platformName} » ?`)) return;

    platforms.splice(index, 1);
    updatePlatformsInYaml(platforms);
}

// Reordonne les plateformes
function reorderPlatforms(oldIndex, newIndex) {
    const platforms = parsePlatformsFromYaml();
    const [removed] = platforms.splice(oldIndex, 1);
    platforms.splice(newIndex, 0, removed);
    updatePlatformsInYaml(platforms);
}

// Met a jour la configuration des plateformes dans le YAML (preserve les commentaires)
function updatePlatformsInYaml(platforms) {
    const editor = document.getElementById('yaml-editor');
    let yaml = editor.value;
    const lines = yaml.split('\n');

    // Trouve l'emplacement de platforms.sources
    let sourcesStart = -1;
    let sourcesEnd = -1;
    let inPlatforms = false;
    let inSources = false;
    let baseIndent = 0;
    let lastDataLineIndex = -1; // Memorise la position de la derniere ligne de donnees

    for (let i = 0; i < lines.length; i++) {
        const line = lines[i];
        const trimmed = line.trim();

        if (line.match(/^platforms:/)) {
            inPlatforms = true;
            continue;
        }

        if (inPlatforms && !inSources && trimmed.startsWith('sources:')) {
            sourcesStart = i + 1;
            inSources = true;
            baseIndent = line.search(/\S/) + 2; // Indentation du niveau sous sources
            continue;
        }

        if (inSources) {
            const currentIndent = line.search(/\S/);

            // Si c'est une ligne de donnees (commence par - ou est un attribut d'element)
            if (trimmed.startsWith('-')) {
                lastDataLineIndex = i;
            } else if (trimmed && !trimmed.startsWith('#') && currentIndent >= baseIndent) {
                // Ligne d'attribut d'element (ex. name:, id:)
                lastDataLineIndex = i;
            } else if (trimmed && !trimmed.startsWith('#') && currentIndent < baseIndent) {
                // Une ligne non commentee moins indentee signifie qu'on a quitte la zone sources
                sourcesEnd = lastDataLineIndex + 1;
                break;
            }
        }

        // Verifie si on entre dans le module de premier niveau suivant
        if (inPlatforms && line.match(/^[a-z_]+:/) && !line.match(/^platforms:/)) {
            if (lastDataLineIndex >= 0) {
                sourcesEnd = lastDataLineIndex + 1;
            } else {
                sourcesEnd = i;
            }
            break;
        }
    }

    // Si aucune fin trouvee, utilise la ligne suivant la derniere ligne de donnees
    if (sourcesEnd === -1) {
        sourcesEnd = lastDataLineIndex >= 0 ? lastDataLineIndex + 1 : lines.length;
    }

    // Extrait les commentaires de la zone (preserve ceux en debut)
    const regionLines = lines.slice(sourcesStart, sourcesEnd);
    const leadingComments = [];
    for (const line of regionLines) {
        const trimmed = line.trim();
        if (trimmed.startsWith('#')) {
            leadingComments.push(line);
        } else if (trimmed.startsWith('-') || (trimmed && !trimmed.startsWith('#'))) {
            // Premier element de donnees rencontre, arret de la collecte des commentaires
            break;
        } else if (trimmed === '') {
            // Les lignes vides sont aussi conservees
            leadingComments.push(line);
        }
    }

    const indent = '    '; // 4 espaces d'indentation
    const newSourcesLines = platforms.map(p =>
        `${indent}- id: "${p.id}"\n${indent}  name: "${p.name}"`
    ).join('\n');

    const beforeSources = lines.slice(0, sourcesStart);
    const afterSources = lines.slice(sourcesEnd);

    // Assemblage : contenu precedent + commentaires d'en-tete + nouvelles donnees + contenu suivant
    const newYaml = [
        ...beforeSources,
        ...(leadingComments.length > 0 ? leadingComments : []),
        newSourcesLines,
        ...afterSources
    ].join('\n');

    editor.value = newYaml;
    currentYaml = newYaml;
    updateBackdrop('yaml-editor', 'yaml-backdrop');
    debounceSaveConfig();
    renderPlatformsList();
    renderStandaloneLists(); // Met a jour la liste de selection des plateformes de la zone autonome
}

// ==========================================
// 12. Fonctions de tri et de gestion des zones d'affichage
// ==========================================

const DISPLAY_REGIONS_DEF = [
    { key: "hotlist", label: "Zone des palmares" },
    { key: "new_items", label: "Zone des nouveautes" },
    { key: "rss", label: "Zone des abonnements RSS" },
    { key: "standalone", label: "Zone autonome" },
    { key: "ai_analysis", label: "Zone d'analyse IA" }
];

// Analyse display.regions depuis le YAML, en suivant strictement l'ordre defini par region_order
function parseDisplayRegionsFromYaml() {
    try {
        const doc = jsyaml.load(currentYaml);
        if (doc && doc.display) {
            const regionOrder = doc.display.region_order || [];
            const regionStates = doc.display.regions || {};

            // Construit la liste en suivant strictement l'ordre region_order
            if (regionOrder.length > 0) {
                return regionOrder.map(key => {
                    const normalizedKey = key === 'new_item' ? 'new_items' : key;
                    const def = DISPLAY_REGIONS_DEF.find(d => d.key === normalizedKey);
                    return {
                        key: normalizedKey,
                        label: def ? def.label : normalizedKey,
                        enabled: regionStates[normalizedKey] !== undefined ? regionStates[normalizedKey] : false
                    };
                });
            }

            // Solution de repli : sans region_order, utilise l'ordre de l'objet regions
            const regions = [];
            for (const key in regionStates) {
                const normalizedKey = key === 'new_item' ? 'new_items' : key;
                const def = DISPLAY_REGIONS_DEF.find(d => d.key === normalizedKey);
                if (def) {
                    regions.push({
                        key: normalizedKey,
                        label: def.label,
                        enabled: regionStates[key]
                    });
                }
            }
            return regions;
        }
    } catch (e) {}

    // Par defaut, renvoie toutes les zones (etat desactive)
    return DISPLAY_REGIONS_DEF.map(def => ({
        key: def.key,
        label: def.label,
        enabled: false
    }));
}

// Affiche la liste des zones d'affichage
function renderDisplayRegionsList() {
    const container = document.getElementById('display-regions-list');
    if (!container) return;

    const regions = parseDisplayRegionsFromYaml();

    container.innerHTML = regions.map((r, idx) => `
        <div class="display-region-item flex items-center justify-between bg-gray-50 rounded-lg px-3 py-2 border border-gray-200 hover:border-blue-300 transition-colors" data-key="${r.key}">
            <div class="flex items-center gap-2">
                <i class="fa-solid fa-grip-vertical text-gray-300 cursor-move"></i>
                <span class="text-xs font-medium ${r.enabled ? 'text-gray-700' : 'text-gray-400'}">${r.label}</span>
                <span class="text-[10px] text-gray-400">(${r.key})</span>
            </div>
            <div class="relative inline-block w-10 align-middle select-none">
                <input type="checkbox" id="toggle-region-${r.key}"
                       ${r.enabled ? 'checked' : ''}
                       onchange="toggleDisplayRegion('${r.key}')"
                       class="toggle-checkbox absolute block w-4 h-4 mt-0.5 ml-0.5 rounded-full bg-white border-4 appearance-none cursor-pointer transition-all duration-200 ease-in-out"/>
                <label for="toggle-region-${r.key}" class="toggle-label block overflow-hidden h-5 rounded-full bg-gray-300 cursor-pointer"></label>
            </div>
        </div>
    `).join('');

    // Initialise le tri par glisser-deposer
    if (typeof Sortable !== 'undefined') {
        new Sortable(container, {
            animation: 150,
            handle: '.fa-grip-vertical',
            onEnd: function(evt) {
                reorderDisplayRegions();
            }
        });
    }
}

// Bascule l'etat d'activation de la zone
window.toggleDisplayRegion = function(key) {
    const regions = parseDisplayRegionsFromYaml();
    const target = regions.find(r => r.key === key);
    if (target) {
        target.enabled = !target.enabled;
        updateDisplayRegionsInYaml(regions);
    }
}

// Reordonne les zones
window.reorderDisplayRegions = function() {
    const container = document.getElementById('display-regions-list');
    const items = container.querySelectorAll('.display-region-item');
    const newOrderKeys = Array.from(items).map(item => item.dataset.key);

    const currentRegions = parseDisplayRegionsFromYaml();

    const newRegions = newOrderKeys.map(key => {
        return currentRegions.find(r => r.key === key);
    }).filter(r => r); // Filtre les eventuels undefined

    updateDisplayRegionsInYaml(newRegions);
}

// Met a jour display.regions et display.region_order dans le YAML
function updateDisplayRegionsInYaml(regions) {
    const editor = document.getElementById('yaml-editor');
    let yaml = editor.value;
    const lines = yaml.split('\n');

    let regionOrderStart = -1;
    let regionOrderEnd = -1;
    let regionsStart = -1;
    let regionsEnd = -1;
    let inDisplay = false;
    let regionOrderIndent = 0;
    let regionsIndent = 0;

    for (let i = 0; i < lines.length; i++) {
        const line = lines[i];
        const trimmed = line.trim();

        if (line.match(/^display:/)) {
            inDisplay = true;
            continue;
        }

        if (!inDisplay) continue;

        // Recherche le tableau region_order
        if (trimmed.startsWith('region_order:')) {
            regionOrderStart = i + 1;
            regionOrderIndent = line.search(/\S/) + 2;
            // Trouve la fin de region_order
            for (let j = i + 1; j < lines.length; j++) {
                const nextLine = lines[j];
                const nextTrimmed = nextLine.trim();
                if (nextTrimmed && !nextTrimmed.startsWith('#') && !nextTrimmed.startsWith('-')) {
                    const nextIndent = nextLine.search(/\S/);
                    if (nextIndent < regionOrderIndent) {
                        regionOrderEnd = j;
                        break;
                    }
                }
            }
            if (regionOrderEnd === -1) regionOrderEnd = lines.length;
            continue;
        }

        // Recherche l'objet regions
        if (trimmed.startsWith('regions:')) {
            regionsStart = i + 1;
            regionsIndent = line.search(/\S/) + 2;
            // Trouve la fin de regions (cle de meme niveau ou superieur)
            for (let j = i + 1; j < lines.length; j++) {
                const nextLine = lines[j];
                const nextTrimmed = nextLine.trim();
                if (nextTrimmed && !nextTrimmed.startsWith('#')) {
                    const nextIndent = nextLine.search(/\S/);
                    // Verifie s'il s'agit d'une cle de meme niveau ou superieur (ex. standalone:)
                    if (nextIndent <= line.search(/\S/)) {
                        regionsEnd = j;
                        break;
                    }
                }
            }
            if (regionsEnd === -1) regionsEnd = lines.length;
            break;
        }

        // Verifie si on quitte le module display
        if (line.match(/^[a-z_]+:/) && !line.match(/^display:/)) {
            break;
        }
    }

    // Met a jour le tableau region_order (preserve les commentaires)
    if (regionOrderStart > 0 && regionOrderEnd > regionOrderStart) {
        const indentStr = ' '.repeat(regionOrderIndent);

        // Extrait la table de correspondance des commentaires des lignes d'origine
        const originalRegionOrderBlock = lines.slice(regionOrderStart, regionOrderEnd);
        const commentMap = {};

        originalRegionOrderBlock.forEach(line => {
            // Correspond au format "- key  # commentaire"
            const match = line.match(/^\s*-\s*([a-z_]+)\s*(#.*)?$/);
            if (match) {
                const key = match[1];
                const comment = match[2] || '';
                if (key) commentMap[key] = comment;
            }
        });

        // Genere les nouvelles lignes en preservant les commentaires
        const newRegionOrderLines = regions.map(r => {
            const comment = commentMap[r.key] || '';
            return `${indentStr}- ${r.key}${comment ? '                       ' + comment : ''}`;
        });

        lines.splice(regionOrderStart, regionOrderEnd - regionOrderStart, ...newRegionOrderLines);

        // Ajuste regionsStart et regionsEnd
        const lineDiff = newRegionOrderLines.length - (regionOrderEnd - regionOrderStart);
        if (regionsStart > regionOrderEnd) {
            regionsStart += lineDiff;
            regionsEnd += lineDiff;
        }
    }

    // Met a jour l'objet regions
    if (regionsStart > 0 && regionsEnd > regionsStart) {
        const originalRegionsBlock = lines.slice(regionsStart, regionsEnd);
        const commentMap = {};

        originalRegionsBlock.forEach(line => {
            const match = line.match(/^\s*([a-z_]+):\s*[^#]*(#.*)?$/);
            if (match) {
                const key = match[1];
                const comment = match[2] || '';
                if (key) commentMap[key] = comment;
            }
        });

        const indentStr = ' '.repeat(regionsIndent);
        const newRegionsLines = regions.map(r => {
            const comment = commentMap[r.key] || '';
            return `${indentStr}${r.key}: ${r.enabled}${comment ? ' ' + comment.trim() : ''}`;
        });

        lines.splice(regionsStart, regionsEnd - regionsStart, ...newRegionsLines);
    }

    editor.value = lines.join('\n');
    currentYaml = lines.join('\n');
    updateBackdrop('yaml-editor', 'yaml-backdrop');
    debounceSaveConfig();

    renderDisplayRegionsList();
}

// Analyse la liste des sources RSS dans la configuration actuelle
function parseRssFeedsFromYaml() {
    try {
        const doc = jsyaml.load(currentYaml);
        if (doc && doc.rss && doc.rss.feeds) {
            return doc.rss.feeds;
        }
    } catch (e) {}
    return [];
}

// Affiche la liste des sources RSS
function renderRssFeedsList() {
    const container = document.getElementById('rss-feeds-list');
    if (!container) return;

    const feeds = parseRssFeedsFromYaml();

    if (feeds.length === 0) {
        container.innerHTML = `<div class="text-xs text-gray-400 italic">Aucune source RSS pour l'instant, veuillez en ajouter</div>`;
        return;
    }

    container.innerHTML = feeds.map((f, idx) => `
        <div class="rss-feed-item bg-gray-50 rounded-lg px-3 py-2 border border-gray-200 hover:border-blue-300 transition-colors" data-index="${idx}">
            <div class="flex items-center justify-between">
                <div class="flex items-center gap-2 flex-1 min-w-0">
                    <i class="fa-solid fa-rss text-orange-400"></i>
                    <span class="text-xs font-medium text-gray-700 truncate">${f.name}</span>
                    <span class="text-[10px] text-gray-400">(${f.id})</span>
                    ${f.enabled === false ? '<span class="text-[9px] bg-gray-200 text-gray-500 px-1 rounded">Desactive</span>' : ''}
                </div>
                <div class="flex items-center gap-1">
                    <button onclick="editRssFeed(${idx})" class="text-blue-400 hover:text-blue-600 text-xs px-1" title="Modifier">
                        <i class="fa-solid fa-pen"></i>
                    </button>
                    <button onclick="toggleRssFeed(${idx})" class="text-gray-400 hover:text-gray-600 text-xs px-1" title="${f.enabled === false ? 'Activer' : 'Desactiver'}">
                        <i class="fa-solid fa-${f.enabled === false ? 'eye' : 'eye-slash'}"></i>
                    </button>
                    <button onclick="removeRssFeed(${idx})" class="text-red-400 hover:text-red-600 text-xs px-1" title="Supprimer">
                        <i class="fa-solid fa-trash"></i>
                    </button>
                </div>
            </div>
            <div class="text-[10px] text-gray-400 mt-1 truncate" title="${f.url}">${f.url}</div>
        </div>
    `).join('');
}

// Supprime une source RSS
window.removeRssFeed = function(index) {
    const feeds = parseRssFeedsFromYaml();
    if (index < 0 || index >= feeds.length) return;

    const feedName = feeds[index].name;
    if (!confirm(`Voulez-vous vraiment supprimer la source RSS "${feedName} » ?`)) return;

    feeds.splice(index, 1);
    updateRssFeedsInYaml(feeds);
}

// Bascule l'etat d'activation de la source RSS
window.toggleRssFeed = function(index) {
    const feeds = parseRssFeedsFromYaml();
    if (index < 0 || index >= feeds.length) return;

    feeds[index].enabled = feeds[index].enabled === false ? true : false;
    updateRssFeedsInYaml(feeds);
}

// Modifier la source RSS
window.editRssFeed = function(index) {
    const feeds = parseRssFeedsFromYaml();
    if (index < 0 || index >= feeds.length) return;

    const feed = feeds[index];

    openRssModalWithData(feed, index);
}

// Met a jour la configuration RSS dans le YAML (preserve les commentaires)
function updateRssFeedsInYaml(feeds) {
    const editor = document.getElementById('yaml-editor');
    let yaml = editor.value;
    const lines = yaml.split('\n');

    // Trouve l'emplacement de rss.feeds
    let feedsStart = -1;
    let feedsEnd = -1;
    let inRss = false;
    let inFeeds = false;
    let lastDataLineIndex = -1; // Memorise la position de la derniere ligne de donnees

    for (let i = 0; i < lines.length; i++) {
        const line = lines[i];
        const trimmed = line.trim();

        if (line.match(/^rss:/)) {
            inRss = true;
            continue;
        }

        if (inRss && !inFeeds && trimmed.startsWith('feeds:')) {
            feedsStart = i + 1;
            inFeeds = true;
            continue;
        }

        if (inFeeds) {
            const indent = line.search(/\S/);

            // Si c'est une ligne de donnees (commence par - ou est un attribut d'element)
            if (trimmed.startsWith('-')) {
                lastDataLineIndex = i;
            } else if (trimmed && !trimmed.startsWith('#') && indent > 2) {
                // Ligne d'attribut d'element (ex. name:, id:, url:)
                lastDataLineIndex = i;
            } else if (trimmed && !trimmed.startsWith('#') && indent <= 2 && indent >= 0) {
                // Une ligne non commentee moins indentee signifie qu'on a quitte la zone feeds
                feedsEnd = lastDataLineIndex + 1;
                break;
            }
        }

        // Verifie si on entre dans le module de premier niveau suivant
        if (inRss && line.match(/^[a-z_]+:/) && !line.match(/^rss:/)) {
            if (lastDataLineIndex >= 0) {
                feedsEnd = lastDataLineIndex + 1;
            } else {
                feedsEnd = i;
            }
            break;
        }
    }

    // Si aucune fin trouvee, utilise la ligne suivant la derniere ligne de donnees
    if (feedsEnd === -1) {
        feedsEnd = lastDataLineIndex >= 0 ? lastDataLineIndex + 1 : lines.length;
    }

    // Extrait les commentaires de la zone (preserve ceux en debut)
    const regionLines = lines.slice(feedsStart, feedsEnd);
    const leadingComments = [];
    for (const line of regionLines) {
        const trimmed = line.trim();
        if (trimmed.startsWith('#')) {
            leadingComments.push(line);
        } else if (trimmed.startsWith('-') || (trimmed && !trimmed.startsWith('#'))) {
            // Premier element de donnees rencontre, arret de la collecte des commentaires
            break;
        } else if (trimmed === '') {
            // Les lignes vides sont aussi conservees
            leadingComments.push(line);
        }
    }

    // Construit le nouveau contenu de feeds
    const indent = '    '; // 4 espaces d'indentation
    const newFeedsLines = feeds.map(f => {
        let feedYaml = `${indent}- id: "${f.id}"\n${indent}  name: "${f.name}"\n${indent}  url: "${f.url}"`;
        if (f.enabled === false) {
            feedYaml += `\n${indent}  enabled: false`;
        }
        if (f.max_age_days !== undefined && f.max_age_days !== '') {
            feedYaml += `\n${indent}  max_age_days: ${f.max_age_days}`;
        }
        return feedYaml;
    }).join('\n\n');

    const beforeFeeds = lines.slice(0, feedsStart);
    const afterFeeds = lines.slice(feedsEnd);

    // Assemblage : contenu precedent + commentaires d'en-tete + nouvelles donnees + ligne vide + contenu suivant
    const newYaml = [
        ...beforeFeeds,
        ...(leadingComments.length > 0 ? leadingComments : []),
        newFeedsLines,
        '',
        ...afterFeeds
    ].join('\n');

    editor.value = newYaml;
    currentYaml = newYaml;
    updateBackdrop('yaml-editor', 'yaml-backdrop');
    debounceSaveConfig();
    renderRssFeedsList();
    renderStandaloneLists(); // Met a jour la liste de selection RSS de la zone autonome
}

// Ouvre la fenetre d'ajout / d'edition RSS
window.openRssModal = function() {
    openRssModalWithData(null, -1);
}

function openRssModalWithData(feed, editIndex) {
    const modal = document.getElementById('rss-modal');

    document.getElementById('rss-id').value = feed ? feed.id : '';
    document.getElementById('rss-name').value = feed ? feed.name : '';
    document.getElementById('rss-url').value = feed ? feed.url : '';
    document.getElementById('rss-max-age').value = feed && feed.max_age_days !== undefined ? feed.max_age_days : '';

    modal.dataset.editIndex = editIndex;

    const title = modal.querySelector('h3');
    if (title) {
        title.innerHTML = editIndex >= 0 ?
            '<i class="fa-solid fa-rss mr-2 text-orange-500"></i>Modifier la source RSS' :
            '<i class="fa-solid fa-rss mr-2 text-orange-500"></i>Ajouter une source RSS';
    }

    modal.classList.remove('hidden');
}

// Ferme la fenetre RSS
window.closeRssModal = function() {
    const modal = document.getElementById('rss-modal');
    modal.classList.add('hidden');
    modal.dataset.editIndex = '-1';

    document.getElementById('rss-id').value = '';
    document.getElementById('rss-name').value = '';
    document.getElementById('rss-url').value = '';
    document.getElementById('rss-max-age').value = '';
}

// Confirme l'ajout / la modification RSS
window.confirmAddRss = function() {
    const modal = document.getElementById('rss-modal');
    const editIndex = parseInt(modal.dataset.editIndex || '-1');

    const id = document.getElementById('rss-id').value.trim();
    const name = document.getElementById('rss-name').value.trim();
    const url = document.getElementById('rss-url').value.trim();
    const maxAge = document.getElementById('rss-max-age').value.trim();

    if (!id || !name || !url) {
        alert('Veuillez renseigner toutes les informations : ID, nom et URL sont obligatoires');
        return;
    }

    const feeds = parseRssFeedsFromYaml();

    const newFeed = { id, name, url };
    if (maxAge) {
        newFeed.max_age_days = parseInt(maxAge);
    }

    if (editIndex >= 0) {
        feeds[editIndex] = newFeed;
    } else {
        feeds.push(newFeed);
    }

    updateRssFeedsInYaml(feeds);
    closeRssModal();
}

// ==========================================
// 14. Fonctions de gestion de la zone autonome (Standalone)
// ==========================================

function parseStandaloneConfigFromYaml() {
    try {
        const doc = jsyaml.load(currentYaml);
        if (doc && doc.display && doc.display.standalone) {
            return {
                platforms: doc.display.standalone.platforms || [],
                rss_feeds: doc.display.standalone.rss_feeds || []
            };
        }
    } catch (e) {}
    return { platforms: [], rss_feeds: [] };
}

function renderStandaloneLists() {
    const platformsContainer = document.getElementById('standalone-platforms-list');
    const rssContainer = document.getElementById('standalone-rss-list');

    if (!platformsContainer || !rssContainer) return;

    const standaloneConfig = parseStandaloneConfigFromYaml();
    const availablePlatforms = parsePlatformsFromYaml();
    const availableRss = parseRssFeedsFromYaml();

    // Render Platforms
    if (availablePlatforms.length === 0) {
        platformsContainer.innerHTML = `<div class="col-span-2 text-xs text-gray-400 italic">Aucune plateforme disponible</div>`;
    } else {
        platformsContainer.innerHTML = availablePlatforms.map(p => {
            const isChecked = standaloneConfig.platforms.includes(p.id);
            return `
                <label class="flex items-center gap-2 p-1.5 rounded hover:bg-white transition-colors cursor-pointer">
                    <input type="checkbox" onchange="toggleStandaloneItem('platforms', '${p.id}')"
                           ${isChecked ? 'checked' : ''} class="rounded border-gray-300 text-blue-600 focus:ring-blue-500">
                    <div class="min-w-0">
                        <div class="text-xs font-medium text-gray-700 truncate">${p.name}</div>
                        <div class="text-[9px] text-gray-400 truncate">${p.id}</div>
                    </div>
                </label>
            `;
        }).join('');
    }

    // Render RSS
    if (availableRss.length === 0) {
        rssContainer.innerHTML = `<div class="text-xs text-gray-400 italic">Aucune source RSS disponible</div>`;
    } else {
        rssContainer.innerHTML = availableRss.map(f => {
            const isChecked = standaloneConfig.rss_feeds.includes(f.id);
            return `
                <label class="flex items-center gap-2 p-1.5 rounded hover:bg-white transition-colors cursor-pointer">
                    <input type="checkbox" onchange="toggleStandaloneItem('rss_feeds', '${f.id}')"
                           ${isChecked ? 'checked' : ''} class="rounded border-gray-300 text-blue-600 focus:ring-blue-500">
                    <div class="min-w-0 flex-1">
                        <div class="flex items-center justify-between">
                            <span class="text-xs font-medium text-gray-700 truncate">${f.name}</span>
                            <span class="text-[9px] text-gray-400 ml-2">${f.id}</span>
                        </div>
                        <div class="text-[9px] text-gray-400 truncate">${f.url}</div>
                    </div>
                </label>
            `;
        }).join('');
    }
}

window.toggleStandaloneItem = function(type, id) {
    const config = parseStandaloneConfigFromYaml();
    const list = config[type];

    const index = list.indexOf(id);
    if (index === -1) {
        list.push(id);
    } else {
        list.splice(index, 1);
    }

    updateStandaloneConfigInYaml(type, list);
}

function updateStandaloneConfigInYaml(type, list) {
    const editor = document.getElementById('yaml-editor');
    let yaml = editor.value;
    const lines = yaml.split('\n');

    // Trouve display -> standalone -> [type]
    let inDisplay = false;
    let inStandalone = false;
    let targetLineIndex = -1;
    let indent = '';

    for (let i = 0; i < lines.length; i++) {
        const line = lines[i];
        if (line.match(/^display:/)) {
            inDisplay = true;
            continue;
        }
        if (inDisplay && line.trim().startsWith('standalone:')) {
            inStandalone = true;
            continue;
        }
        if (inStandalone) {
            // Verifie si on quitte standalone (ligne non commentee de meme indentation ou moins)
            const currentIndent = line.search(/\S/);
            // Indentation du niveau sous standalone
            if (line.match(new RegExp(`^\\s*${type}:`))) {
                targetLineIndex = i;
                indent = line.substring(0, line.indexOf(type));
                break;
            }
            // Si on atteint le module suivant, on s'arrete
            if (line.match(/^[a-z_]+:/) && !line.match(/^display:/)) break;
        }
    }

    if (targetLineIndex !== -1) {
        // Construit la nouvelle chaine de tableau ["item1", "item2"]
        const jsonStr = JSON.stringify(list);
        // Preserve le commentaire existant
        const originalLine = lines[targetLineIndex];
        const commentMatch = originalLine.match(/#.*$/);
        const comment = commentMatch ? commentMatch[0] : '';

        lines[targetLineIndex] = `${indent}${type}: ${jsonStr}${comment ? ' ' + comment : ''}`;

        const newYaml = lines.join('\n');
        editor.value = newYaml;
        currentYaml = newYaml;
        updateBackdrop('yaml-editor', 'yaml-backdrop');
        debounceSaveConfig();

        // Pas besoin de reafficher toute la liste, car declenche par un clic sur une case a cocher
        // Mais pour garantir la coherence, on peut reafficher
    }
}


// Extrait le numero de version du texte
function extractVersion(text) {
    // Correspond au format Version: v5.3.0 ou Version: 5.3.0
    const versionMatch = text.match(/Version:\s*v?(\d+\.\d+\.\d+)/i);
    if (versionMatch) {
        return versionMatch[1]; // Renvoie le numero de version sans le v
    }
    return null;
}

// Compare les numeros de version (renvoie 1 : v1 > v2, -1 : v1 < v2, 0 : v1 == v2)
function compareVersions(v1, v2) {
    if (!v1 || !v2) return 0;

    const parts1 = v1.split('.').map(Number);
    const parts2 = v2.split('.').map(Number);

    for (let i = 0; i < Math.max(parts1.length, parts2.length); i++) {
        const num1 = parts1[i] || 0;
        const num2 = parts2[i] || 0;

        if (num1 > num2) return 1;
        if (num1 < num2) return -1;
    }

    return 0;
}

// Fonction principale de verification de version
window.checkVersion = async function() {
    const btn = document.getElementById('version-check-btn');
    const originalHTML = btn.innerHTML;

    btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i><span>Verification...</span>';
    btn.disabled = true;

    try {
        const versionRes = await fetchWithFallback(REMOTE_VERSION_URL);
        if (!versionRes.ok) {
            throw new Error(`Echec de recuperation des informations de version : ${versionRes.status}`);
        }

        const versionConfigText = await versionRes.text();
        const versionMap = {};
        versionConfigText.split('\n').forEach(line => {
            const parts = line.trim().split('=');
            if (parts.length >= 2) {
                versionMap[parts[0].trim()] = parts[1].trim();
            }
        });

        const currentTab = getCurrentTab();
        let currentVersion = null;
        let fileName = '';

        if (currentTab === 'config') {
            currentVersion = extractVersion(currentYaml);
            fileName = 'config.yaml';
        } else {
            currentVersion = extractVersion(currentFrequency);
            fileName = 'frequency_words.txt';
        }

        const latestVersion = versionMap[fileName];

        if (!latestVersion) {
             throw new Error(`Introuvable dans la liste des versions distantes : ${fileName}`);
        }

        showVersionComparisonModal(fileName, currentVersion, latestVersion);

    } catch (err) {
        console.error('Echec de la verification de version :', err);
        showToast(`Echec de la verification de version : ${err.message}`, 'error');
    } finally {
        btn.innerHTML = originalHTML;
        btn.disabled = false;
    }
}

// Recupere l'onglet actuel
function getCurrentTab() {
    return currentTab; 
}

// Affiche la fenetre de comparaison de versions
function showVersionComparisonModal(fileName, currentVersion, latestVersion) {
    const existingModal = document.getElementById('version-comparison-modal');
    if (existingModal) existingModal.remove();

    const comparison = compareVersions(currentVersion, latestVersion);
    let statusIcon = '';
    let statusText = '';
    let statusColor = '';
    let actionButtons = '';

    if (!currentVersion) {
        statusIcon = '<i class="fa-solid fa-question-circle text-gray-500 text-3xl"></i>';
        statusText = 'Aucune information de version detectee';
        statusColor = 'text-gray-600';
        actionButtons = `
            <button onclick="closeVersionModal()" class="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded-lg">Fermer</button>
            <button onclick="updateToLatest()" class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700">
                <i class="fa-solid fa-download mr-1"></i>Mettre a jour vers la derniere version
            </button>
        `;
    } else if (comparison < 0) {
        statusIcon = '<i class="fa-solid fa-arrow-up text-orange-500 text-3xl"></i>';
        statusText = 'Nouvelle version disponible';
        statusColor = 'text-orange-600';
        actionButtons = `
            <button onclick="closeVersionModal()" class="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded-lg">Mettre a jour plus tard</button>
            <button onclick="updateToLatest()" class="px-4 py-2 bg-orange-600 text-white rounded-lg hover:bg-orange-700">
                <i class="fa-solid fa-download mr-1"></i>Mettre a jour maintenant
            </button>
        `;
    } else if (comparison > 0) {
        statusIcon = '<i class="fa-solid fa-flask text-purple-500 text-3xl"></i>';
        statusText = 'La version actuelle est plus recente (version de developpement ?)';
        statusColor = 'text-purple-600';
        actionButtons = `
            <button onclick="closeVersionModal()" class="px-4 py-2 bg-gray-100 text-gray-600 hover:bg-gray-200 rounded-lg">Fermer</button>
        `;
    } else {
        statusIcon = '<i class="fa-solid fa-check-circle text-green-500 text-3xl"></i>';
        statusText = 'Deja a la derniere version';
        statusColor = 'text-green-600';
        actionButtons = `
            <button onclick="closeVersionModal()" class="px-4 py-2 bg-gray-100 text-gray-600 hover:bg-gray-200 rounded-lg">Fermer</button>
        `;
    }

    const modal = document.createElement('div');
    modal.id = 'version-comparison-modal';
    modal.className = 'modal-overlay';
    modal.innerHTML = `
        <div class="modal-content" style="max-width: 480px;">
            <div class="flex items-center justify-between mb-4">
                <h3 class="text-lg font-bold text-gray-800">
                    <i class="fa-solid fa-code-compare mr-2 text-blue-500"></i>Resultat de la verification de version
                </h3>
                <button onclick="closeVersionModal()" class="text-gray-400 hover:text-gray-600">
                    <i class="fa-solid fa-times text-xl"></i>
                </button>
            </div>

            <div class="text-center py-6">
                ${statusIcon}
                <div class="text-xl font-bold ${statusColor} mt-3">${statusText}</div>
            </div>

            <div class="bg-gray-50 rounded-lg p-4 space-y-3 mb-4">
                <div class="flex items-center justify-between text-sm">
                    <span class="text-gray-600">Fichier de configuration</span>
                    <span class="font-mono font-bold text-gray-800">${fileName}</span>
                </div>
                <div class="border-t border-gray-200"></div>
                <div class="flex items-center justify-between text-sm">
                    <span class="text-gray-600">Version actuelle</span>
                    <span class="font-mono font-bold ${currentVersion ? 'text-blue-600' : 'text-gray-400'}">
                        ${currentVersion ? 'v' + currentVersion : 'Inconnue'}
                    </span>
                </div>
                <div class="flex items-center justify-between text-sm">
                    <span class="text-gray-600">Derniere version</span>
                    <span class="font-mono font-bold text-green-600">v${latestVersion}</span>
                </div>
            </div>

            ${comparison < 0 || !currentVersion ? `
                <div class="text-xs text-gray-500 bg-yellow-50 border border-yellow-200 rounded p-3 mb-4">
                    <i class="fa-solid fa-lightbulb mr-1 text-yellow-600"></i>
                    <strong>Astuce : </strong>La mise a jour chargera depuis GitHub la derniere version de ${fileName} ; vos modifications actuelles seront ecrasees. Pensez a copier et sauvegarder votre configuration personnalisee au prealable.
                </div>
            ` : ''}

            <div class="flex justify-end gap-2">
                ${actionButtons}
            </div>
        </div>
    `;

    document.body.appendChild(modal);
}

window.closeVersionModal = function() {
    const modal = document.getElementById('version-comparison-modal');
    if (modal) modal.remove();
}

// ==========================================
// 13. Logique de la fenetre d'ajout de plateforme
// ==========================================

// Liste predefinie des plateformes disponibles (uniquement celles prises en charge par defaut officiellement)
const PRESET_PLATFORMS = [
    { key: 'toutiao', name: 'Toutiao' },
    { key: 'baidu', name: 'Recherches populaires Baidu' },
    { key: 'wallstreetcn-hot', name: 'Wallstreetcn' },
    { key: 'thepaper', name: 'The Paper' },
    { key: 'bilibili-hot-search', name: 'Recherches populaires Bilibili' },
    { key: 'cls-hot', name: 'CLS Populaire' },
    { key: 'ifeng', name: 'ifeng' },
    { key: 'tieba', name: 'Tieba' },
    { key: 'weibo', name: 'Weibo' },
    { key: 'douyin', name: 'Douyin' },
    { key: 'zhihu', name: 'Zhihu' }
];

/**
 * Ouvre la fenetre d'ajout de plateforme
 */
window.openPlatformModal = function() {
    const modal = document.getElementById('platform-modal');
    if (modal) {
        modal.classList.remove('hidden');
        if (typeof switchPlatformTab === 'function') {
            switchPlatformTab('select');
        }
        renderAvailablePlatforms();
    }
}

/**
 * Ferme la fenetre d'ajout de plateforme
 */
window.closePlatformModal = function() {
    const modal = document.getElementById('platform-modal');
    if (modal) {
        modal.classList.add('hidden');
    }
}

/**
 * Bascule l'onglet d'ajout de plateforme
 */
window.switchPlatformTab = function(tab) {
    currentPlatformTab = tab;

    // Met a jour le style des onglets
    const tabSelect = document.getElementById('tab-platform-select');
    const tabCustom = document.getElementById('tab-platform-custom');

    if (tab === 'select') {
        if (tabSelect) {
            tabSelect.classList.add('text-blue-600', 'border-blue-600');
            tabSelect.classList.remove('text-gray-500', 'border-transparent');
        }
        if (tabCustom) {
            tabCustom.classList.remove('text-blue-600', 'border-blue-600');
            tabCustom.classList.add('text-gray-500', 'border-transparent');
        }

        const selectPanel = document.getElementById('platform-select-panel');
        const customPanel = document.getElementById('platform-custom-panel');
        if (selectPanel) selectPanel.classList.remove('hidden');
        if (customPanel) customPanel.classList.add('hidden');
    } else {
        if (tabCustom) {
            tabCustom.classList.add('text-blue-600', 'border-blue-600');
            tabCustom.classList.remove('text-gray-500', 'border-transparent');
        }
        if (tabSelect) {
            tabSelect.classList.remove('text-blue-600', 'border-blue-600');
            tabSelect.classList.add('text-gray-500', 'border-transparent');
        }

        const selectPanel = document.getElementById('platform-select-panel');
        const customPanel = document.getElementById('platform-custom-panel');
        if (selectPanel) selectPanel.classList.add('hidden');
        if (customPanel) customPanel.classList.remove('hidden');
    }
}

/**
 * Affiche la liste des plateformes disponibles (hors celles deja ajoutees)
 */
function renderAvailablePlatforms() {
    const container = document.getElementById('available-platforms-list');
    const tip = document.getElementById('no-platforms-tip');
    if (!container) return;
    container.innerHTML = '';

    const currentPlatforms = parsePlatformsFromYaml();
    const existingKeys = currentPlatforms.map(p => p.id); 

    const available = PRESET_PLATFORMS.filter(p => !existingKeys.includes(p.key));

    if (available.length === 0) {
        if (tip) {
            tip.classList.remove('hidden');
            tip.innerHTML = `<i class="fa-solid fa-check-circle text-green-500 mr-2"></i>Toutes les plateformes predefinies sont deja ajoutees`;
        }
    } else {
        if (tip) tip.classList.add('hidden');

        available.forEach(p => {
            const div = document.createElement('div');
            div.className = 'flex items-center justify-between p-3 border border-gray-100 rounded hover:bg-blue-50 cursor-pointer transition-colors group';
            div.onclick = () => confirmAddPlatform(p.key, p.name);
            div.innerHTML = `
                <div class="flex items-center gap-3">
                    <div class="w-8 h-8 rounded bg-gray-100 flex items-center justify-center text-gray-500 group-hover:bg-white group-hover:text-blue-600">
                        <i class="fa-solid fa-cube"></i>
                    </div>
                    <div>
                        <div class="font-bold text-gray-800 text-sm">${p.name}</div>
                        <div class="text-xs text-gray-400 font-mono">${p.key}</div>
                    </div>
                </div>
                <button class="text-gray-300 group-hover:text-blue-600">
                    <i class="fa-solid fa-plus-circle text-lg"></i>
                </button>
            `;
            container.appendChild(div);
        });
    }
}

/**
 * Confirme l'ajout de plateforme
 */
window.confirmAddPlatform = function(key, name) {
    let platformKey = key;
    let platformName = name;

    // Si on est en mode saisie manuelle (et qu'aucune cle n'est fournie)
    if (currentPlatformTab === 'custom' && !key) {
        const keyInput = document.getElementById('custom-platform-key');
        const nameInput = document.getElementById('custom-platform-name');

        if (keyInput) platformKey = keyInput.value.trim();
        if (nameInput) platformName = nameInput.value.trim();

        if (!platformKey) {
            alert('Veuillez saisir la cle de la plateforme');
            return;
        }
        if (!platformName) {
            platformName = platformKey;
        }
    } else if (currentPlatformTab === 'select' && !key) {
        alert("Cliquez directement sur une plateforme de la liste ci-dessus pour l'ajouter");
        return;
    }

    // Verifie si elle existe deja
    const currentPlatforms = parsePlatformsFromYaml();
    if (currentPlatforms.find(p => p.id === platformKey)) {
        alert(`La plateforme ${platformKey} existe deja !`);
        return;
    }

    // Ajoute au YAML (attention : les champs sont id et name)
    const newPlatform = {
        id: platformKey,
        name: platformName,
        enabled: true
    };

    // Reconstruit le YAML
    currentPlatforms.push(newPlatform);
    updatePlatformsInYaml(currentPlatforms);

    closePlatformModal();

    const keyInput = document.getElementById('custom-platform-key');
    const nameInput = document.getElementById('custom-platform-name');
    if (keyInput) keyInput.value = '';
    if (nameInput) nameInput.value = '';

    renderPlatformsList();

    showToast(`La plateforme ${platformName} ajoutee`, 'success');
}

// Lie au scope global
window.updateToLatest = async function() {
    closeVersionModal();

    const currentTab = getCurrentTab();
    const fileName = currentTab === 'config' ? 'config.yaml' : 'frequency_words.txt';

    if (!confirm(`Voulez-vous vraiment mettre a jour ${fileName} depuis GitHub vers la derniere version ?\n\nVotre configuration personnalisee actuelle sera ecrasee ; pensez a la copier et la sauvegarder au prealable.`)) {
        return;
    }

    showToast('Chargement de la derniere version...', 'info');

    try {
        const url = currentTab === 'config' ? REMOTE_CONFIG_URL : REMOTE_FREQUENCY_URL;
        const res = await fetchWithFallback(url);

        if (!res.ok) {
            throw new Error(`Echec du chargement : ${res.status}`);
        }

        const text = await res.text();

        if (currentTab === 'config') {
            try {
                jsyaml.load(text);
            } catch (yamlErr) {
                showToast(`Erreur de syntaxe YAML : ${yamlErr.message}`, 'error');
                return;
            }
            document.getElementById('yaml-editor').value = text;
            currentYaml = text;
            syncYamlToUI();
        } else {
            document.getElementById('frequency-editor').value = text;
            currentFrequency = text;
            syncFrequencyToUI();
        }

        saveToLocalStorage();

        showToast(`Mis a jour vers la derniere version`, 'success');

    } catch (err) {
        console.error('Echec de la mise a jour :', err);
        showToast(`Echec de la mise a jour : ${err.message}`, 'error');
    }
}

// ==========================================
// Fonctions auxiliaires RSS
// ==========================================

function toggleRssTips() {
    const panel = document.getElementById('rss-tips-panel');
    const icon = document.getElementById('rss-tips-icon');
    if (panel) {
        panel.classList.toggle('hidden');
        if (icon) {
            icon.style.transform = panel.classList.contains('hidden') ? 'rotate(0deg)' : 'rotate(180deg)';
        }
    }
}

function fillRssUrl(url) {
    const input = document.getElementById('rss-url');
    if (input) {
        input.value = url;
        // Retour visuel
        input.classList.add('ring-2', 'ring-blue-500', 'bg-blue-50');
        setTimeout(() => {
            input.classList.remove('ring-2', 'ring-blue-500', 'bg-blue-50');
        }, 500);
    }
}

// ==========================================
// 13. Fonctions de l'editeur Timeline
// ==========================================

const PRESET_META = {
    morning_evening: { icon: 'fa-sun', color: 'text-amber-500', bg: 'bg-amber-50', recommend: true },
    always_on:       { icon: 'fa-bolt', color: 'text-blue-500', bg: 'bg-blue-50' },
    office_hours:    { icon: 'fa-briefcase', color: 'text-green-500', bg: 'bg-green-50' },
    night_owl:       { icon: 'fa-moon', color: 'text-indigo-500', bg: 'bg-indigo-50' },
    custom:          { icon: 'fa-sliders', color: 'text-purple-500', bg: 'bg-purple-50' }
};

const DAY_NAMES = ['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Dim'];

/**
 * Lit schedule.preset depuis le config.yaml actuel
 */
function getActivePreset() {
    try {
        const doc = jsyaml.load(currentYaml);
        return doc?.schedule?.preset || 'morning_evening';
    } catch { return 'morning_evening'; }
}

/**
 * Analyse le YAML timeline et renvoie des donnees structurees
 */
function parseTimelineData() {
    try {
        const doc = jsyaml.load(currentTimeline);
        if (!doc) return null;
        return doc;
    } catch { return null; }
}

/**
 * Recupere la configuration complete du preset / custom indique
 */
function getPresetConfig(data, presetName) {
    if (!data) return null;
    if (presetName === 'custom') return data.custom || null;
    return data.presets?.[presetName] || null;
}

/**
 * Fonction de rendu principale : analyse le YAML timeline → affiche le panneau de droite
 */
function syncTimelineToUI() {
    const panel = document.getElementById('timeline-panel');
    if (!panel) return;

    const data = parseTimelineData();
    const activePreset = getActivePreset();

    if (!data) {
        panel.innerHTML = `
            <div class="text-center py-12 text-gray-400">
                <i class="fa-solid fa-calendar-xmark text-4xl mb-3"></i>
                <p class="text-sm">Collez le contenu de timeline.yaml a gauche</p>
                <p class="text-xs mt-1">Ou cliquez en haut a droite sur « Charger la derniere configuration officielle »</p>
            </div>`;
        return;
    }

    let html = '';

    // ── Layer 1: Carte de selection du mode predefini ──
    html += `<div class="mb-6">
        <div class="tl-section-title"><i class="fa-solid fa-swatchbook"></i>Mode de planification</div>
        <div class="grid grid-cols-2 gap-3" id="tl-preset-grid">`;

    // Collecte tous les noms de preset
    const presetNames = Object.keys(data.presets || {});
    // S'assure que custom est en dernier
    const allModes = [...presetNames.filter(n => n !== 'custom'), ...(data.custom ? ['custom'] : [])];

    allModes.forEach(name => {
        const meta = PRESET_META[name] || { icon: 'fa-puzzle-piece', color: 'text-gray-500', bg: 'bg-gray-50' };
        const presetCfg = getPresetConfig(data, name);
        const label = presetCfg?.name || meta.label || name;
        const desc = presetCfg?.description || meta.desc || '';
        const isActive = name === activePreset;
        const isProtected = ['morning_evening', 'always_on', 'office_hours', 'night_owl', 'custom'].includes(name);
        html += `
            <div class="tl-preset-card ${isActive ? 'selected' : ''}" data-preset="${name}">
                ${meta.recommend ? '<div class="tl-recommend-badge">Recommande</div>' : ''}
                <div class="flex items-center gap-3 cursor-pointer" onclick="selectTimelinePreset('${name}')">
                    <div class="tl-card-icon ${meta.bg} ${meta.color}"><i class="fa-solid ${meta.icon}"></i></div>
                    <div class="flex-1 min-w-0">
                        <div class="text-sm font-bold text-gray-800 truncate tl-editable" ondblclick="event.stopPropagation();tlInlineEdit(this,'${name}','name','${escapeAttr(label)}')">${label}</div>
                        <div class="text-[10px] text-gray-500 truncate tl-editable" ondblclick="event.stopPropagation();tlInlineEdit(this,'${name}','description','${escapeAttr(desc)}')">${desc}</div>
                    </div>
                </div>
                <div class="tl-card-actions">
                    <button onclick="event.stopPropagation();duplicateTlPreset('${name}')" class="tl-card-action-btn" title="Copier"><i class="fa-regular fa-copy"></i></button>
                    ${!isProtected ? `<button onclick="event.stopPropagation();deleteTlPreset('${name}')" class="tl-card-action-btn text-red-400 hover:text-red-600" title="Supprimer"><i class="fa-regular fa-trash-can"></i></button>` : ''}
                </div>
                ${isActive ? '<div class="absolute bottom-1 right-2 text-[9px] text-blue-500 font-bold"><i class="fa-solid fa-check-circle mr-0.5"></i>Actuel</div>' : ''}
            </div>`;
    });

    // Carte de creation de mode
    html += `
        <div class="tl-preset-card tl-new-preset-card" onclick="openTlNewPresetModal()">
            <div class="flex items-center gap-3">
                <div class="tl-card-icon bg-gray-50 text-gray-400"><i class="fa-solid fa-plus"></i></div>
                <div>
                    <div class="text-sm font-bold text-gray-500">Nouveau mode</div>
                    <div class="text-[10px] text-gray-400">Creer un schema de planification personnalise</div>
                </div>
            </div>
        </div>`;

    html += `</div></div>`;

    // Recupere la configuration du preset actuel
    const config = getPresetConfig(data, activePreset);

    if (!config) {
        html += `<div class="text-center py-6 text-gray-400 text-sm">
            <i class="fa-solid fa-triangle-exclamation text-amber-400 mr-1"></i>
            Configuration introuvable pour le preset « ${activePreset} »
        </div>`;
        panel.innerHTML = html;
        return;
    }

    // ── Layer 2: Chronologie de la vue hebdomadaire ──
    html += renderWeekView(config, activePreset);

    // ── Layer 3 : details des plages horaires ──
    html += renderPeriodDetails(config, activePreset);

    panel.innerHTML = html;

    // Initialise le tri par glisser-deposer des etiquettes de plan journalier
    initDayPlanSortable(activePreset);
}

/**
 * Affiche la vue hebdomadaire (barres horizontales 7 jours x 24 heures)
 */
function renderWeekView(config, presetName) {
    const periods = config.periods || {};
    const dayPlans = config.day_plans || {};
    const weekMap = config.week_map || {};

    // Graduation horaire
    let html = `<div class="tl-week-view">
        <div class="tl-section-title mb-2"><i class="fa-solid fa-calendar-week"></i>Vue hebdomadaire</div>
        <div class="tl-hour-markers">
            <div style="width:2.5rem;flex-shrink:0"></div>
            <div style="flex:1;display:flex;min-width:480px">`;

    for (let h = 0; h <= 24; h += 2) {
        html += `<div class="tl-hour-marker" style="width:${100/12}%;${h===24?'text-align:right;margin-left:-1em':''}">
            ${h < 10 ? '0' : ''}${h}
        </div>`;
    }
    html += `</div></div>`;

    // Recupere le jour de la semaine actuel (1 = lundi... 7 = dimanche)
    const today = new Date().getDay();
    const todayIso = today === 0 ? 7 : today;

    // Lignes des 7 jours
    for (let d = 1; d <= 7; d++) {
        const dayPlanName = weekMap[d] || weekMap[String(d)];
        const dayPlan = dayPlans[dayPlanName];
        const dayPeriodNames = dayPlan?.periods || [];
        const isToday = d === todayIso;

        html += `<div class="tl-week-row">
            <div class="tl-day-label ${isToday ? 'today' : ''}">${DAY_NAMES[d-1]}</div>
            <div class="tl-timeline-bar" data-day="${d}" onclick="onTlBarClick(event,'${presetName}',${d})">`;

        // Affiche les blocs de couleur de chaque plage horaire
        dayPeriodNames.forEach(pName => {
            const p = periods[pName];
            if (!p) return;

            const merged = mergeWithDefault(p, config.default);
            const colorClass = getBlockColorClass(merged);
            const blocks = computeBlocks(p.start, p.end);

            blocks.forEach(b => {
                const left = (b.start / 24 * 100).toFixed(2);
                const width = ((b.end - b.start) / 24 * 100).toFixed(2);
                const label = p.name || pName;
                html += `<div class="tl-period-block ${colorClass}" style="left:${left}%;width:${width}%"
                              onclick="scrollToPeriodCard('${pName}')"
                              onmouseenter="showTlTooltip(event, '${escapeAttr(label)}', '${p.start||''}', '${p.end||''}', ${!!merged.push}, ${!!merged.analyze}, '${merged.report_mode||''}')"
                              onmouseleave="hideTlTooltip()">
                    <span class="tl-block-label">${label}</span>
                </div>`;
            });
        });

        // Ligne indiquant l'heure actuelle (aujourd'hui uniquement)
        if (isToday) {
            const nowTime = new Date();
            const nowH = nowTime.getHours() + nowTime.getMinutes() / 60;
            const nowLeftPct = (nowH / 24 * 100).toFixed(2);
            html += `<div class="tl-now-line" style="left:${nowLeftPct}%" title="Heure actuelle ${String(nowTime.getHours()).padStart(2,'0')}:${String(nowTime.getMinutes()).padStart(2,'0')}"></div>`;
        }

        html += `</div></div>`;
    }

    // Legende
    html += `<div class="tl-legend">
        <div class="tl-legend-item"><div class="tl-legend-color tl-block-push"></div>Notification</div>
        <div class="tl-legend-item"><div class="tl-legend-color tl-block-analyze"></div>Analyse IA</div>
        <div class="tl-legend-item"><div class="tl-legend-color tl-block-push-analyze"></div>Notification + analyse</div>
        <div class="tl-legend-item"><div class="tl-legend-color tl-block-collect"></div>Collecte seule</div>
        <div class="tl-legend-item"><div class="tl-legend-color" style="background:#f1f5f9;border:1px solid #e2e8f0"></div>Par defaut (default)</div>
    </div>`;

    html += `</div>`;
    return html;
}

/**
 * Fusionne period et default (les champs de period priment)
 */
function mergeWithDefault(period, defaultCfg) {
    if (!defaultCfg) return period || {};
    const merged = { ...defaultCfg, ...period };
    if (period.once || defaultCfg.once) {
        merged.once = { ...(defaultCfg.once || {}), ...(period.once || {}) };
    }
    return merged;
}

/**
 * Determine la classe CSS du bloc selon l'etat push/analyze
 */
function getBlockColorClass(merged) {
    const push = !!merged.push;
    const analyze = !!merged.analyze;
    if (push && analyze) return 'tl-block-push-analyze';
    if (push) return 'tl-block-push';
    if (analyze) return 'tl-block-analyze';
    if (merged.collect !== false) return 'tl-block-collect';
    return 'tl-block-silent';
}

/**
 * Calcule les blocs de rendu d'une plage (gere le passage de minuit)
 * Renvoie un tableau [{start: heure, end: heure}, ...]
 */
function computeBlocks(startStr, endStr) {
    if (!startStr || !endStr) return [];
    const s = parseTime(startStr);
    const e = parseTime(endStr);
    if (s < e) return [{ start: s, end: e }];
    // Franchit minuit
    return [{ start: s, end: 24 }, { start: 0, end: e }];
}

function parseTime(str) {
    const [h, m] = (str || '00:00').split(':').map(Number);
    return h + (m || 0) / 60;
}

function escapeAttr(s) {
    return (s || '').replace(/'/g, "\\'").replace(/"/g, '&quot;');
}

/**
 * Affichage / masquage de l'info-bulle
 */
let tlTooltipEl = null;

function showTlTooltip(event, name, start, end, push, analyze, mode) {
    hideTlTooltip();
    const el = document.createElement('div');
    el.className = 'tl-tooltip';
    let features = [];
    if (push) features.push('<span style="color:#93c5fd">Notification</span>');
    if (analyze) features.push('<span style="color:#c4b5fd">Analyse</span>');
    if (!push && !analyze) features.push('<span style="color:#94a3b8">Collecte seule</span>');

    el.innerHTML = `<div style="font-weight:700;margin-bottom:2px">${name}</div>
        <div style="font-size:11px;color:#9ca3af">${start} - ${end}</div>
        <div style="margin-top:4px">${features.join(' / ')}</div>
        ${mode ? `<div style="font-size:10px;color:#9ca3af;margin-top:2px">Mode : ${mode}</div>` : ''}`;

    document.body.appendChild(el);
    tlTooltipEl = el;

    const rect = event.target.getBoundingClientRect();
    el.style.left = (rect.left + rect.width / 2 - el.offsetWidth / 2) + 'px';
    el.style.top = (rect.top - el.offsetHeight - 8) + 'px';

    // S'assure de ne pas depasser l'ecran
    const elRect = el.getBoundingClientRect();
    if (elRect.left < 4) el.style.left = '4px';
    if (elRect.right > window.innerWidth - 4) el.style.left = (window.innerWidth - el.offsetWidth - 4) + 'px';
    if (elRect.top < 4) {
        el.style.top = (rect.bottom + 8) + 'px';
        el.style.setProperty('--arrow', 'top');
    }
}

function hideTlTooltip() {
    if (tlTooltipEl) {
        tlTooltipEl.remove();
        tlTooltipEl = null;
    }
}

/**
 * Affiche le panneau de details des plages horaires
 */
function renderPeriodDetails(config, presetName) {
    const isCustom = presetName === 'custom';
    const periods = config.periods || {};
    const dayPlans = config.day_plans || {};
    const weekMap = config.week_map || {};
    const defaults = config.default || {};

    let html = '';

    // ── Configuration default (deployee par defaut)──
    html += `<div class="tl-collapsible mt-4">
        <div class="tl-collapsible-header" onclick="toggleTlCollapsible(this)">
            <span><i class="fa-solid fa-gear mr-2 text-gray-400"></i>Configuration par defaut (default)</span>
            <i class="fa-solid fa-chevron-down text-gray-400 text-xs"></i>
        </div>
        <div class="tl-collapsible-body">
            <div class="text-xs text-gray-500 mb-2">Lorsqu'aucune plage horaire ne s'applique, on utilise la configuration suivante :</div>
            ${renderBehaviorToggles(defaults, presetName, 'default', defaults)}
        </div>
    </div>`;

    // ── Liste des plages horaires ──
    const periodEntries = Object.entries(periods);
    html += `<div class="mt-6">
        <div class="tl-section-title flex items-center justify-between">
            <span><i class="fa-solid fa-puzzle-piece"></i>Plages horaires (Periods)</span>
            <button onclick="openTlNewPeriodModal('${presetName}')" class="tl-add-btn"><i class="fa-solid fa-plus mr-1"></i>Ajouter</button>
        </div>`;

    if (periodEntries.length > 0) {
        html += `<div class="space-y-3">`;
        periodEntries.forEach(([key, p]) => {
            const merged = mergeWithDefault(p, defaults);
            const colorClass = getBlockColorClass(merged);
            html += `<div class="tl-period-card" id="tl-period-${key}">
                <div class="flex items-center justify-between mb-2">
                    <div class="flex items-center gap-2">
                        <div class="w-3 h-3 rounded ${colorClass}"></div>
                        <span class="text-sm font-bold text-gray-800 tl-editable" ondblclick="tlInlineEditPeriod(this,'${presetName}','${key}','${escapeAttr(p.name || key)}')">${p.name || key}</span>
                        <span class="text-[10px] text-gray-400 font-mono">${key}</span>
                    </div>
                    <div class="flex items-center gap-2">
                        <span class="text-xs text-gray-500 font-mono">${p.start || '?'} - ${p.end || '?'}</span>
                        <button onclick="duplicateTlPeriod('${presetName}','${key}')" class="tl-inline-btn" title="Copier"><i class="fa-regular fa-copy"></i></button>
                        <button onclick="deleteTlPeriod('${presetName}','${key}')" class="tl-inline-btn text-red-400 hover:text-red-600" title="Supprimer"><i class="fa-regular fa-trash-can"></i></button>
                    </div>
                </div>
                ${renderBehaviorToggles(merged, presetName, key, p)}
            </div>`;
        });
        html += `</div>`;
    } else {
        html += `<div class="text-xs text-gray-400 text-center py-4">
            <i class="fa-solid fa-info-circle mr-1"></i>Ce mode n'a pas de plage horaire personnalisee ; la configuration default s'applique toute la journee
        </div>`;
    }

    html += `</div>`;

    // ── Plans journaliers ──
    const dayPlanEntries = Object.entries(dayPlans);
    html += `<div class="mt-6">
        <div class="tl-section-title flex items-center justify-between">
            <span><i class="fa-solid fa-list-ol"></i>Plans journaliers (Day Plans)</span>
            <button onclick="addTlDayPlan('${presetName}')" class="tl-add-btn"><i class="fa-solid fa-plus mr-1"></i>Ajouter</button>
        </div>`;

    if (dayPlanEntries.length > 0) {
        html += `<div class="space-y-2">`;
        dayPlanEntries.forEach(([name, plan]) => {
            const pList = plan.periods || [];
            // Construit la liste deroulante des plages disponibles (hors celles deja ajoutees)
            const availablePeriods = periodEntries.filter(([k]) => !pList.includes(k));
            html += `<div class="bg-white border border-gray-200 rounded-lg px-3 py-2 tl-dayplan-card">
                <div class="flex items-center justify-between mb-1">
                    <span class="text-xs font-bold text-gray-700">${name}</span>
                    <button onclick="deleteTlDayPlan('${presetName}','${name}')" class="tl-inline-btn text-red-400 hover:text-red-600" title="Supprimer le plan journalier"><i class="fa-regular fa-trash-can"></i></button>
                </div>
                <div class="flex flex-wrap gap-1 items-center tl-dayplan-sortable" data-plan-key="${name}">
                    ${pList.length > 0 ? pList.map(pn => {
                        const p = periods[pn];
                        const merged = p ? mergeWithDefault(p, defaults) : {};
                        const cc = getBlockColorClass(merged);
                        return `<span class="tl-period-tag ${cc}" data-period-key="${pn}">
                            ${p?.name || pn}
                            <button onclick="removePeriodFromDayPlanUI('${presetName}','${name}','${pn}')" class="tl-tag-remove" title="Retirer">&times;</button>
                        </span>`;
                    }).join('') : '<span class="text-[10px] text-gray-400">Vide (default toute la journee)</span>'}
                    ${availablePeriods.length > 0 ? `
                        <select class="tl-add-period-select" onchange="if(this.value){addPeriodToDayPlan('${presetName}','${name}',this.value);this.value=''}">
                            <option value="">+ Ajouter</option>
                            ${availablePeriods.map(([k, p]) => `<option value="${k}">${p.name || k}</option>`).join('')}
                        </select>
                    ` : ''}
                </div>
            </div>`;
        });
        html += `</div>`;
    }

    html += `</div>`;

    // ── Correspondance hebdomadaire (liste deroulante)──
    const dayPlanKeys = Object.keys(dayPlans);

    // Attribue une couleur a chaque plan journalier
    const planColorMap = {};
    const planColors = ['bg-blue-50 border-blue-200', 'bg-green-50 border-green-200', 'bg-amber-50 border-amber-200', 'bg-purple-50 border-purple-200', 'bg-rose-50 border-rose-200', 'bg-cyan-50 border-cyan-200', 'bg-orange-50 border-orange-200'];
    dayPlanKeys.forEach((k, idx) => { planColorMap[k] = planColors[idx % planColors.length]; });

    html += `<div class="mt-6">
        <div class="tl-section-title"><i class="fa-solid fa-calendar-days"></i>Correspondance hebdomadaire (Week Map)</div>
        <div class="bg-white border border-gray-200 rounded-lg px-3 py-2 space-y-1">`;

    for (let d = 1; d <= 7; d++) {
        const plan = weekMap[d] || weekMap[String(d)] || '';
        const rowColor = planColorMap[plan] || '';
        const options = dayPlanKeys.map(k =>
            `<option value="${k}" ${k === plan ? 'selected' : ''}>${k}</option>`
        ).join('');
        html += `<div class="tl-dayplan-row ${rowColor} rounded px-2">
            <div class="tl-dayplan-label">${DAY_NAMES[d-1]}</div>
            <select class="tl-weekmap-select"
                    onchange="onTlWeekMap('${presetName}',${d},this.value)">
                ${options}
            </select>
        </div>`;
    }

    html += `</div>
        <div class="flex gap-2 mt-2">
            <button onclick="tlWeekMapQuick('${presetName}','all_same')" class="tl-quick-btn">Toute la semaine identique</button>
            <button onclick="tlWeekMapQuick('${presetName}','weekday_same')" class="tl-quick-btn">Jours ouvres identiques</button>
            <button onclick="tlWeekMapQuick('${presetName}','weekday_weekend')" class="tl-quick-btn">Jours ouvres / week-end</button>
        </div>
    </div>`;

    // Specifique a custom : strategie de conflit de plages
    if (isCustom) {
        const overlapPolicy = (config.overlap && config.overlap.policy) || 'error_on_overlap';
        html += `<div class="mt-6">
            <div class="tl-section-title"><i class="fa-solid fa-code-branch"></i>Strategie de conflit (Overlap)</div>
            <div class="bg-white border border-gray-200 rounded-lg px-3 py-3">
                <div class="flex items-center gap-2">
                    <span class="text-xs text-gray-500">policy:</span>
                    <select class="text-xs border border-gray-200 rounded px-2 py-1 bg-white"
                            onchange="onTlCustomOverlapPolicy(this.value)">
                        <option value="error_on_overlap" ${overlapPolicy === 'error_on_overlap' ? 'selected' : ''}>error_on_overlap (recommande)</option>
                        <option value="last_wins" ${overlapPolicy === 'last_wins' ? 'selected' : ''}>last_wins (le dernier defini prime)</option>
                    </select>
                </div>
                <div class="text-[10px] text-gray-400 mt-2">
                    <i class="fa-solid fa-info-circle mr-1"></i>
                    <code>error_on_overlap</code> genere une erreur en cas de chevauchement de plages ; <code>last_wins</code> applique la plage definie en dernier dans day_plans.
                </div>
            </div>
        </div>`;
    }

    // Astuce
    if (!isCustom) {
        html += `<div class="mt-4 text-xs text-gray-400 p-3 bg-gray-50 rounded-lg border border-gray-200">
            <i class="fa-solid fa-lightbulb mr-1 text-amber-400"></i>
            Ajustez directement les interrupteurs et listes deroulantes ci-dessus, le YAML de gauche se met a jour automatiquement. Pour un controle plus fin, editez directement le YAML de gauche ou modifiez <strong>timeline.yaml</strong>.
        </div>`;
    } else {
        html += `<div class="mt-4 text-xs text-gray-400 p-3 bg-purple-50 rounded-lg border border-purple-200">
            <i class="fa-solid fa-pen-ruler mr-1 text-purple-400"></i>
            Le mode personnalise autorise une edition totalement libre. Ajustez les controles ci-dessus ou editez le texte YAML a gauche : les deux cotes sont synchronises en temps reel.
        </div>`;
    }

    return html;
}

/**
 * Affiche les interrupteurs de comportement (interactifs)
 * presetName : nom du preset actuel (sert a localiser la position dans le YAML)
 * periodKey : 'default' ou cle de plage horaire (ex. 'weekday_morning')
 */
function renderBehaviorToggles(cfg, presetName, periodKey, rawCfg = null) {
    const toggleItems = [
        { k: 'collect', label: 'Collecte', icon: 'fa-download' },
        { k: 'analyze', label: 'Analyse', icon: 'fa-brain' },
        { k: 'push', label: 'Notification', icon: 'fa-bell' },
    ];

    const uid = `tl-${presetName}-${periodKey}`;

    let html = '<div class="tl-toggle-row">';
    toggleItems.forEach(item => {
        const val = cfg[item.k];
        const on = val === true || val === 'true';
        const toggleId = `${uid}-${item.k}`;
        html += `<label class="tl-toggle-item ${on ? 'on' : 'off'}" for="${toggleId}" style="cursor:pointer">
            <div class="relative inline-block w-8 mr-1 align-middle select-none">
                <input type="checkbox" id="${toggleId}" ${on ? 'checked' : ''}
                    onchange="onTlToggle('${presetName}','${periodKey}','${item.k}',this.checked)"
                    class="toggle-checkbox absolute block w-4 h-4 rounded-full bg-white border-4 appearance-none cursor-pointer transition-all duration-200 ease-in-out" style="top:0"/>
                <label for="${toggleId}" class="toggle-label block overflow-hidden h-4 rounded-full bg-gray-300 cursor-pointer"></label>
            </div>
            <i class="fa-solid ${item.icon}" style="font-size:10px"></i>${item.label}
        </label>`;
    });
    html += '</div>';

    // Liste deroulante du mode de rapport
    const reportModes = ['current', 'daily', 'incremental'];
    const aiModes = ['follow_report', 'daily', 'current', 'incremental'];

    html += `<div class="flex flex-wrap gap-2 mt-2 items-center">`;

    // report_mode
    html += `<div class="flex items-center gap-1">
        <span class="text-[10px] text-gray-400">Rapport :</span>
        <select class="text-[10px] border border-gray-200 rounded px-1 py-0.5 bg-white"
                onchange="onTlSelect('${presetName}','${periodKey}','report_mode',this.value)">
            ${reportModes.map(m => `<option value="${m}" ${cfg.report_mode === m ? 'selected' : ''}>${m}</option>`).join('')}
        </select>
    </div>`;

    // ai_mode
    html += `<div class="flex items-center gap-1">
        <span class="text-[10px] text-gray-400">AI:</span>
        <select class="text-[10px] border border-gray-200 rounded px-1 py-0.5 bg-white"
                onchange="onTlSelect('${presetName}','${periodKey}','ai_mode',this.value)">
            ${aiModes.map(m => `<option value="${m}" ${(cfg.ai_mode || 'follow_report') === m ? 'selected' : ''}>${m}</option>`).join('')}
        </select>
    </div>`;

    // once toggles
    const onceAnalyze = cfg.once?.analyze === true;
    const oncePush = cfg.once?.push === true;
    html += `<label class="flex items-center gap-1 text-[10px] ${onceAnalyze ? 'text-blue-600' : 'text-gray-400'}" style="cursor:pointer">
        <input type="checkbox" ${onceAnalyze ? 'checked' : ''}
               onchange="onTlToggle('${presetName}','${periodKey}','once.analyze',this.checked)"
               class="w-3 h-3 rounded">Analyser une seule fois
    </label>`;
    html += `<label class="flex items-center gap-1 text-[10px] ${oncePush ? 'text-blue-600' : 'text-gray-400'}" style="cursor:pointer">
        <input type="checkbox" ${oncePush ? 'checked' : ''}
               onchange="onTlToggle('${presetName}','${periodKey}','once.push',this.checked)"
               class="w-3 h-3 rounded">Notifier une seule fois
    </label>`;

    html += `</div>`;

    // Edition de la plage (sauf default)
    if (periodKey !== 'default' && (cfg.start || cfg.end)) {
        html += `<div class="flex items-center gap-2 mt-2">
            <span class="text-[10px] text-gray-400">Heure :</span>
            <input type="time" value="${cfg.start || ''}" class="text-xs border border-gray-200 rounded px-1.5 py-0.5"
                   onchange="onTlSelect('${presetName}','${periodKey}','start',this.value)">
            <span class="text-gray-300">~</span>
            <input type="time" value="${cfg.end || ''}" class="text-xs border border-gray-200 rounded px-1.5 py-0.5"
                   onchange="onTlSelect('${presetName}','${periodKey}','end',this.value)">
        </div>`;
    }

    // Surcharge de filtrage optionnelle (affiche uniquement les champs du « niveau courant » pour eviter de confondre une valeur heritee avec une configuration explicite)
    const baseCfg = rawCfg || {};
    const filterMethod = baseCfg.filter_method || '';
    const frequencyFile = baseCfg.frequency_file || '';
    const interestsFile = baseCfg.interests_file || '';
    const methodHint = periodKey === 'default' ? 'Si vide, suit le filter.method global' : 'Si vide, herite de default (puis repli sur le global)';

    html += `<div class="mt-3 pt-3 border-t border-gray-100">
        <div class="text-[10px] uppercase tracking-wider font-bold text-gray-400 mb-2">Surcharge de filtrage (optionnel)</div>
        <div class="grid grid-cols-1 md:grid-cols-3 gap-2">
            <div>
                <label class="block text-[10px] text-gray-400 mb-1">filter_method</label>
                <select class="text-[10px] w-full border border-gray-200 rounded px-1.5 py-1 bg-white"
                        onchange="onTlOptionalSelect('${presetName}','${periodKey}','filter_method',this.value)">
                    <option value="" ${filterMethod === '' ? 'selected' : ''}>Heriter</option>
                    <option value="keyword" ${filterMethod === 'keyword' ? 'selected' : ''}>keyword</option>
                    <option value="ai" ${filterMethod === 'ai' ? 'selected' : ''}>ai</option>
                </select>
            </div>
            <div>
                <label class="block text-[10px] text-gray-400 mb-1">frequency_file</label>
                <input type="text" value="${frequencyFile}" placeholder="ex. tech.txt"
                       class="text-[10px] w-full border border-gray-200 rounded px-1.5 py-1 bg-white"
                       onchange="onTlOptionalInput('${presetName}','${periodKey}','frequency_file',this.value)">
            </div>
            <div>
                <label class="block text-[10px] text-gray-400 mb-1">interests_file</label>
                <input type="text" value="${interestsFile}" placeholder="ex. geopolitics.txt"
                       class="text-[10px] w-full border border-gray-200 rounded px-1.5 py-1 bg-white"
                       onchange="onTlOptionalInput('${presetName}','${periodKey}','interests_file',this.value)">
            </div>
        </div>
        <div class="text-[10px] text-gray-400 mt-2">
            <i class="fa-solid fa-lightbulb mr-1"></i>${methodHint}. <code>frequency_file</code> est recherche dans <code>config/custom/keyword/</code>, 
            <code>interests_file</code> est recherche dans <code>config/custom/ai/</code> ; laisser vide supprime le champ et retablit l'heritage.
        </div>
    </div>`;

    return html;
}

/**
 * Clic sur un bloc de la vue hebdomadaire → defile vers la carte de la plage correspondante et la met en surbrillance
 */
window.scrollToPeriodCard = function(periodKey) {
    const card = document.getElementById('tl-period-' + periodKey);
    if (!card) return;
    card.scrollIntoView({ behavior: 'smooth', block: 'center' });
    card.classList.add('tl-period-highlight');
    setTimeout(() => card.classList.remove('tl-period-highlight'), 1500);
}

/**
 * Bascule replier / deplier
 */
window.toggleTlCollapsible = function(header) {
    const body = header.nextElementSibling;
    body.classList.toggle('collapsed');
    header.classList.toggle('is-collapsed');
}

/**
 * Changement d'un interrupteur a droite → met a jour le YAML timeline a gauche
 */
window.onTlToggle = function(presetName, periodKey, field, value) {
    updateTimelineField(presetName, periodKey, field, value);
}

window.onTlSelect = function(presetName, periodKey, field, value) {
    updateTimelineField(presetName, periodKey, field, value);
}

window.onTlOptionalInput = function(presetName, periodKey, field, rawValue) {
    const value = (rawValue || '').trim();
    if (!value) {
        removeTimelineField(presetName, periodKey, field);
        return;
    }
    updateTimelineField(presetName, periodKey, field, value);
}

window.onTlOptionalSelect = function(presetName, periodKey, field, value) {
    if (!value) {
        removeTimelineField(presetName, periodKey, field);
        return;
    }
    updateTimelineField(presetName, periodKey, field, value);
}

window.onTlCustomOverlapPolicy = function(value) {
    updateTimelineSectionField('custom', 'overlap.policy', value);
}

/**
 * Changement d'une liste deroulante de correspondance → met a jour week_map.N dans le YAML timeline
 */
window.onTlWeekMap = function(presetName, dayNum, value) {
    const editor = document.getElementById('timeline-editor');
    let yaml = editor.value;
    const lines = yaml.split('\n');

    // Localise la section du preset
    const isCustom = presetName === 'custom';
    let sectionStart = -1;
    let sectionIndent = 0;

    if (isCustom) {
        for (let i = 0; i < lines.length; i++) {
            if (/^custom:\s*/.test(lines[i])) { sectionStart = i; break; }
        }
    } else {
        let inPresets = false;
        for (let i = 0; i < lines.length; i++) {
            const line = lines[i];
            if (/^presets:\s*/.test(line)) { inPresets = true; continue; }
            if (inPresets && /^\S/.test(line) && !line.startsWith('#')) break;
            if (inPresets) {
                const m = line.match(/^(\s+)(\S+):\s*/);
                if (m && m[2] === presetName) { sectionStart = i; sectionIndent = m[1].length; break; }
            }
        }
    }

    if (sectionStart < 0) return;

    let sectionEnd = lines.length;
    for (let i = sectionStart + 1; i < lines.length; i++) {
        const line = lines[i];
        if (line.trim() === '' || line.trim().startsWith('#')) continue;
        if (line.search(/\S/) <= sectionIndent) { sectionEnd = i; break; }
    }

    // Recherche la ligne week_map:
    const weekMapLine = findChildKey(lines, sectionStart, sectionEnd, sectionIndent, 'week_map');
    if (weekMapLine < 0) return;

    const wmIndent = lines[weekMapLine].search(/\S/);
    const wmEnd = findBlockEnd(lines, weekMapLine, wmIndent, sectionEnd);

    // Recherche la ligne dayNum:
    const dayKey = String(dayNum);
    const dayLine = findChildKey(lines, weekMapLine, wmEnd, wmIndent, dayKey);

    if (dayLine >= 0) {
        replaceLineValue(lines, dayLine, value);
    }

    editor.value = lines.join('\n');
    currentTimeline = editor.value;
    updateBackdrop('timeline-editor', 'timeline-backdrop');
    debounceSaveTimeline();

    clearTimeout(window._tlRenderTimer);
    window._tlRenderTimer = setTimeout(() => syncTimelineToUI(), 300);
}

/**
 * Cle : modifie le champ indique dans le YAML timeline en preservant les commentaires
 */
function updateTimelineField(presetName, periodKey, field, value) {
    const editor = document.getElementById('timeline-editor');
    let yaml = editor.value;
    const lines = yaml.split('\n');

    // 1. Localise la ligne de debut du preset / custom
    const isCustom = presetName === 'custom';
    let sectionStart = -1;
    let sectionIndent = 0;

    if (isCustom) {
        // Recherche la cle de premier niveau custom:
        for (let i = 0; i < lines.length; i++) {
            if (/^custom:\s*/.test(lines[i])) {
                sectionStart = i;
                sectionIndent = 0;
                break;
            }
        }
    } else {
        // Recherche presetName: sous presets:
        let inPresets = false;
        for (let i = 0; i < lines.length; i++) {
            const line = lines[i];
            if (/^presets:\s*/.test(line)) {
                inPresets = true;
                continue;
            }
            if (inPresets && /^\S/.test(line) && !line.startsWith('#')) {
                break; // left presets block
            }
            if (inPresets) {
                const m = line.match(/^(\s+)(\S+):\s*/);
                if (m && m[2] === presetName) {
                    sectionStart = i;
                    sectionIndent = m[1].length;
                    break;
                }
            }
        }
    }

    if (sectionStart < 0) return;

    // 2. Trouve la ligne de fin de la section
    let sectionEnd = lines.length;
    for (let i = sectionStart + 1; i < lines.length; i++) {
        const line = lines[i];
        if (line.trim() === '' || line.trim().startsWith('#')) continue;
        const indent = line.search(/\S/);
        if (indent <= sectionIndent) {
            sectionEnd = i;
            break;
        }
    }

    // 3. Localise la sous-zone periodKey dans la section
    let targetStart, targetEnd;
    const fieldParts = field.split('.');

    if (periodKey === 'default') {
        // Recherche la ligne default:
        targetStart = findChildKey(lines, sectionStart, sectionEnd, sectionIndent, 'default');
    } else {
        // Recherche periodKey: sous periods:
        const periodsLine = findChildKey(lines, sectionStart, sectionEnd, sectionIndent, 'periods');
        if (periodsLine < 0) return;
        const periodsIndent = lines[periodsLine].search(/\S/);
        const periodsEnd = findBlockEnd(lines, periodsLine, periodsIndent, sectionEnd);
        targetStart = findChildKey(lines, periodsLine, periodsEnd, periodsIndent, periodKey);
    }

    if (targetStart < 0) return;

    const targetIndent = lines[targetStart].search(/\S/);
    targetEnd = findBlockEnd(lines, targetStart, targetIndent, sectionEnd);

    // 4. Recherche field dans target (gere l'imbrication once.analyze)
    let lineIdx = -1;

    if (fieldParts.length === 1) {
        lineIdx = findChildKey(lines, targetStart, targetEnd, targetIndent, fieldParts[0]);
    } else {
        // nested: once.analyze → find once: then analyze:
        const parentLine = findChildKey(lines, targetStart, targetEnd, targetIndent, fieldParts[0]);
        if (parentLine >= 0) {
            const parentIndent = lines[parentLine].search(/\S/);
            const parentEnd = findBlockEnd(lines, parentLine, parentIndent, targetEnd);
            lineIdx = findChildKey(lines, parentLine, parentEnd, parentIndent, fieldParts[1]);
        }
    }

    if (lineIdx < 0) {
        // Le champ n'existe pas → il faut l'inserer
        insertTimelineField(lines, targetStart, targetEnd, targetIndent, field, value, fieldParts);
    } else {
        // Le champ existe → remplacement de la valeur sur place
        replaceLineValue(lines, lineIdx, value);
    }

    editor.value = lines.join('\n');
    currentTimeline = editor.value;
    updateBackdrop('timeline-editor', 'timeline-backdrop');
    debounceSaveTimeline();

    // Rendu differe (evite un rafraichissement en pleine saisie)
    clearTimeout(window._tlRenderTimer);
    window._tlRenderTimer = setTimeout(() => syncTimelineToUI(), 300);
}

function resolveTimelineSection(lines, presetName) {
    const isCustom = presetName === 'custom';
    let sectionStart = -1;
    let sectionIndent = 0;

    if (isCustom) {
        for (let i = 0; i < lines.length; i++) {
            if (/^custom:\s*/.test(lines[i])) {
                sectionStart = i;
                sectionIndent = 0;
                break;
            }
        }
    } else {
        let inPresets = false;
        for (let i = 0; i < lines.length; i++) {
            const line = lines[i];
            if (/^presets:\s*/.test(line)) {
                inPresets = true;
                continue;
            }
            if (inPresets && /^\S/.test(line) && !line.startsWith('#')) {
                break;
            }
            if (inPresets) {
                const m = line.match(/^(\s+)(\S+):\s*/);
                if (m && m[2] === presetName) {
                    sectionStart = i;
                    sectionIndent = m[1].length;
                    break;
                }
            }
        }
    }

    if (sectionStart < 0) return null;

    let sectionEnd = lines.length;
    for (let i = sectionStart + 1; i < lines.length; i++) {
        const line = lines[i];
        if (line.trim() === '' || line.trim().startsWith('#')) continue;
        const indent = line.search(/\S/);
        if (indent <= sectionIndent) {
            sectionEnd = i;
            break;
        }
    }

    return { sectionStart, sectionEnd, sectionIndent };
}

function resolveTimelineTarget(lines, presetName, periodKey) {
    const section = resolveTimelineSection(lines, presetName);
    if (!section) return null;

    const { sectionStart, sectionEnd, sectionIndent } = section;
    let targetStart = -1;

    if (periodKey === 'default') {
        targetStart = findChildKey(lines, sectionStart, sectionEnd, sectionIndent, 'default');
    } else {
        const periodsLine = findChildKey(lines, sectionStart, sectionEnd, sectionIndent, 'periods');
        if (periodsLine < 0) return null;
        const periodsIndent = lines[periodsLine].search(/\S/);
        const periodsEnd = findBlockEnd(lines, periodsLine, periodsIndent, sectionEnd);
        targetStart = findChildKey(lines, periodsLine, periodsEnd, periodsIndent, periodKey);
    }

    if (targetStart < 0) return null;

    const targetIndent = lines[targetStart].search(/\S/);
    const targetEnd = findBlockEnd(lines, targetStart, targetIndent, sectionEnd);

    return { sectionStart, sectionEnd, sectionIndent, targetStart, targetEnd, targetIndent };
}

function applyTimelineEditorChanges(editor, lines) {
    editor.value = lines.join('\n');
    currentTimeline = editor.value;
    updateBackdrop('timeline-editor', 'timeline-backdrop');
    debounceSaveTimeline();
    clearTimeout(window._tlRenderTimer);
    window._tlRenderTimer = setTimeout(() => syncTimelineToUI(), 300);
}

function removeTimelineField(presetName, periodKey, field) {
    const editor = document.getElementById('timeline-editor');
    const lines = editor.value.split('\n');
    const target = resolveTimelineTarget(lines, presetName, periodKey);
    if (!target) return;

    const { targetStart, targetEnd, targetIndent } = target;
    const fieldParts = field.split('.');

    if (fieldParts.length === 1) {
        const lineIdx = findChildKey(lines, targetStart, targetEnd, targetIndent, fieldParts[0]);
        if (lineIdx < 0) return;
        const lineIndent = lines[lineIdx].search(/\S/);
        const lineEnd = findBlockEnd(lines, lineIdx, lineIndent, targetEnd);
        lines.splice(lineIdx, lineEnd - lineIdx);
        applyTimelineEditorChanges(editor, lines);
        return;
    }

    const parentLine = findChildKey(lines, targetStart, targetEnd, targetIndent, fieldParts[0]);
    if (parentLine < 0) return;
    const parentIndent = lines[parentLine].search(/\S/);
    const parentEnd = findBlockEnd(lines, parentLine, parentIndent, targetEnd);
    const childLine = findChildKey(lines, parentLine, parentEnd, parentIndent, fieldParts[1]);
    if (childLine < 0) return;

    const childIndent = lines[childLine].search(/\S/);
    const childEnd = findBlockEnd(lines, childLine, childIndent, parentEnd);
    lines.splice(childLine, childEnd - childLine);

    const parentEndAfter = findBlockEnd(lines, parentLine, parentIndent, targetEnd);
    let hasChild = false;
    for (let i = parentLine + 1; i < parentEndAfter; i++) {
        const line = lines[i];
        if (line.trim() === '' || line.trim().startsWith('#')) continue;
        if (line.search(/\S/) > parentIndent) {
            hasChild = true;
            break;
        }
    }
    if (!hasChild) {
        lines.splice(parentLine, 1);
    }

    applyTimelineEditorChanges(editor, lines);
}

function updateTimelineSectionField(presetName, field, value) {
    const editor = document.getElementById('timeline-editor');
    const lines = editor.value.split('\n');
    const section = resolveTimelineSection(lines, presetName);
    if (!section) return;

    const { sectionStart, sectionEnd, sectionIndent } = section;
    const fieldParts = field.split('.');
    let lineIdx = -1;

    if (fieldParts.length === 1) {
        lineIdx = findChildKey(lines, sectionStart, sectionEnd, sectionIndent, fieldParts[0]);
    } else {
        const parentLine = findChildKey(lines, sectionStart, sectionEnd, sectionIndent, fieldParts[0]);
        if (parentLine >= 0) {
            const parentIndent = lines[parentLine].search(/\S/);
            const parentEnd = findBlockEnd(lines, parentLine, parentIndent, sectionEnd);
            lineIdx = findChildKey(lines, parentLine, parentEnd, parentIndent, fieldParts[1]);
        }
    }

    if (lineIdx < 0) {
        insertTimelineField(lines, sectionStart, sectionEnd, sectionIndent, field, value, fieldParts);
    } else {
        replaceLineValue(lines, lineIdx, value);
    }

    applyTimelineEditorChanges(editor, lines);
}

/**
 * Recherche la ligne de cle enfant
 */
function findChildKey(lines, start, end, parentIndent, key) {
    for (let i = start + 1; i < end; i++) {
        const line = lines[i];
        if (line.trim() === '' || line.trim().startsWith('#')) continue;
        const indent = line.search(/\S/);
        if (indent <= parentIndent) break;
        const m = line.match(/^\s*(\S+):\s*/);
        const rawKey = m ? m[1].replace(/^["']|["']$/g, '') : null;
        if (m && rawKey === key && indent === parentIndent + 2) {
            return i;
        }
    }
    return -1;
}

/**
 * Trouve le numero de ligne de fin d'un bloc (prochaine ligne non vide et non commentee de meme niveau ou moins indentee)
 */
function findBlockEnd(lines, start, indent, maxEnd) {
    for (let i = start + 1; i < maxEnd; i++) {
        const line = lines[i];
        if (line.trim() === '' || line.trim().startsWith('#')) continue;
        const curIndent = line.search(/\S/);
        if (curIndent <= indent) return i;
    }
    return maxEnd;
}

/**
 * Remplace la valeur dans la ligne en preservant le commentaire
 */
function replaceLineValue(lines, idx, value) {
    const original = lines[idx];
    const match = original.match(/^(\s*\S+:\s*)(.*)$/);
    if (!match) return;

    const prefix = match[1];
    const rest = match[2];
    const commentMatch = rest.match(/(\s*#.*)$/);
    const comment = commentMatch ? commentMatch[1] : '';

    let formatted;
    if (typeof value === 'boolean') {
        formatted = value ? 'true' : 'false';
    } else if (typeof value === 'string') {
        // Verifie si la valeur d'origine comporte des guillemets
        const valPart = rest.slice(0, rest.length - comment.length).trim();
        const isQuoted = (valPart.startsWith('"') && valPart.endsWith('"')) ||
                         (valPart.startsWith("'") && valPart.endsWith("'"));
        if (isQuoted || value.includes(':') || value.includes('#') || value.includes(' ')) {
            formatted = `"${value}"`;
        } else {
            formatted = value;
        }
    } else {
        formatted = String(value);
    }

    lines[idx] = `${prefix}${formatted}${comment}`;
}

/**
 * Lorsque le champ n'existe pas, insere une nouvelle ligne
 */
function insertTimelineField(lines, targetStart, targetEnd, targetIndent, field, value, fieldParts) {
    const indent = ' '.repeat(targetIndent + 2);

    let formatted;
    if (typeof value === 'boolean') formatted = value ? 'true' : 'false';
    else if (typeof value === 'string') formatted = value.includes(':') ? `"${value}"` : value;
    else formatted = String(value);

    if (fieldParts.length === 1) {
        // Insere directement a la fin de target
        lines.splice(targetEnd, 0, `${indent}${field}: ${formatted}`);
    } else {
        // once.analyze → find or create once: block, then insert child
        const parentLine = findChildKey(lines, targetStart, targetEnd, targetIndent, fieldParts[0]);
        if (parentLine >= 0) {
            const parentIndent = lines[parentLine].search(/\S/);
            const parentEnd = findBlockEnd(lines, parentLine, parentIndent, targetEnd);
            const childIndent = ' '.repeat(parentIndent + 2);
            lines.splice(parentEnd, 0, `${childIndent}${fieldParts[1]}: ${formatted}`);
        } else {
            // parent doesn't exist → create both
            lines.splice(targetEnd, 0,
                `${indent}${fieldParts[0]}:`,
                `${indent}  ${fieldParts[1]}: ${formatted}`
            );
        }
    }
}

/**
 * Clic sur une carte de preset → met a jour schedule.preset dans config.yaml + defile l'editeur de gauche
 */
window.selectTimelinePreset = function(name) {
    // Met a jour schedule.preset dans config.yaml
    const configEditor = document.getElementById('yaml-editor');
    let yaml = configEditor.value;
    const lines = yaml.split('\n');

    let presetLineIdx = -1;
    let inSchedule = false;

    for (let i = 0; i < lines.length; i++) {
        const line = lines[i];
        if (/^schedule:\s*$/.test(line.trimEnd()) || /^schedule:\s*#/.test(line)) {
            inSchedule = true;
            continue;
        }
        if (inSchedule && /^\S/.test(line) && !line.startsWith('#')) {
            inSchedule = false;
        }
        if (inSchedule && /^\s+preset:\s*/.test(line)) {
            presetLineIdx = i;
            break;
        }
    }

    if (presetLineIdx >= 0) {
        const original = lines[presetLineIdx];
        const match = original.match(/^(\s*preset:\s*)(.*)$/);
        if (match) {
            const prefix = match[1];
            const rest = match[2];
            const commentMatch = rest.match(/(\s*#.*)$/);
            const comment = commentMatch ? commentMatch[1] : '';
            lines[presetLineIdx] = `${prefix}"${name}"${comment}`;
        }
    }

    configEditor.value = lines.join('\n');
    currentYaml = configEditor.value;
    updateBackdrop('yaml-editor', 'yaml-backdrop');
    debounceSaveConfig();

    // L'editeur timeline de gauche saute au preset correspondant
    scrollTimelineEditorToPreset(name);

    // Reaffiche le panneau timeline
    syncTimelineToUI();
    const tlData = parseTimelineData();
    const tlCfg = getPresetConfig(tlData, name);
    const displayName = tlCfg?.name || name;
    showToast(`Bascule vers le mode « ${displayName} »`, 'success');
}

/**
 * Defile l'editeur timeline de gauche jusqu'a la position du preset correspondant
 */
function scrollTimelineEditorToPreset(presetName) {
    const editor = document.getElementById('timeline-editor');
    const text = editor.value;
    const lines = text.split('\n');

    let targetLine = -1;

    if (presetName === 'custom') {
        // Recherche custom: de premier niveau
        for (let i = 0; i < lines.length; i++) {
            if (/^custom:\s*/.test(lines[i])) {
                targetLine = i;
                break;
            }
        }
    } else {
        // Recherche presetName: sous presets:
        let inPresets = false;
        for (let i = 0; i < lines.length; i++) {
            const line = lines[i];
            if (/^presets:\s*/.test(line)) {
                inPresets = true;
                continue;
            }
            if (inPresets && /^\S/.test(line) && !line.startsWith('#')) break;
            if (inPresets) {
                const m = line.match(/^\s+(\S+):\s*/);
                if (m && m[1] === presetName) {
                    targetLine = i;
                    break;
                }
            }
        }
    }

    if (targetLine < 0) return;

    const lineHeight = EDITOR_LINE_HEIGHT;
    const scrollPosition = targetLine * lineHeight;

    // Definit la position du curseur
    let charCount = 0;
    for (let i = 0; i < targetLine; i++) {
        charCount += lines[i].length + 1;
    }

    editor.focus();
    editor.setSelectionRange(charCount, charCount + lines[targetLine].length);
    editor.scrollTop = scrollPosition - 50;

    // Surbrillance clignotante (evite les conflits de clics rapides)
    clearTimeout(window._tlEditorFlashTimer);
    editor.style.transition = 'background-color 0.3s';
    editor.style.backgroundColor = '#2d4a7c';
    window._tlEditorFlashTimer = setTimeout(() => { editor.style.backgroundColor = ''; }, 300);
}

// ==========================================
// 14. Fonctions CRUD Timeline (creation de mode / plage horaire / plan journalier / suppression, etc.)
// ==========================================

// ── Fenetre : nouveau mode de planification ──

window.openTlNewPresetModal = function() {
    const modal = document.getElementById('tl-new-preset-modal');
    // Remplit la liste deroulante des modeles
    const sel = document.getElementById('tl-new-preset-template');
    const data = parseTimelineData();
    sel.innerHTML = '<option value="">Modele vierge (collecte seule, sans notification ni analyse)</option>';
    if (data?.presets) {
        Object.keys(data.presets).forEach(k => {
            const name = data.presets[k]?.name || k;
            sel.innerHTML += `<option value="${k}">${name} (${k})</option>`;
        });
    }
    if (data?.custom) {
        sel.innerHTML += `<option value="custom">${data.custom.name || 'Personnalise'} (custom)</option>`;
    }
    // Vide les saisies
    document.getElementById('tl-new-preset-key').value = '';
    document.getElementById('tl-new-preset-name').value = '';
    document.getElementById('tl-new-preset-desc').value = '';
    sel.value = '';
    modal.classList.remove('hidden');
}

window.closeTlNewPresetModal = function() {
    document.getElementById('tl-new-preset-modal').classList.add('hidden');
}

window.confirmTlNewPreset = function() {
    const key = document.getElementById('tl-new-preset-key').value.trim();
    const name = document.getElementById('tl-new-preset-name').value.trim();
    const desc = document.getElementById('tl-new-preset-desc').value.trim();
    const template = document.getElementById('tl-new-preset-template').value;

    // Validation
    if (!key) { showToast("Veuillez saisir l'identifiant du mode (key)", 'error'); return; }
    if (!/^[a-zA-Z_][a-zA-Z0-9_]*$/.test(key)) { showToast("La cle n'accepte que lettres, chiffres et underscores, et ne peut pas commencer par un chiffre", 'error'); return; }
    if (!name) { showToast('Veuillez saisir le nom affiche', 'error'); return; }

    // Verifie les doublons
    const data = parseTimelineData();
    if (data?.presets?.[key]) { showToast(`Le preset « ${key} » existe deja`, 'error'); return; }
    if (key === 'custom') { showToast('Impossible d\'utiliser "custom" comme nom de preset', 'error'); return; }

    // Construit le bloc de texte YAML
    let block;
    if (template && data) {
        const src = getPresetConfig(data, template);
        if (src) {
            block = buildPresetYamlBlock(key, { ...src, name: name, description: desc || src.description || '' });
        } else {
            block = buildEmptyPresetBlock(key, name, desc);
        }
    } else {
        block = buildEmptyPresetBlock(key, name, desc);
    }

    // Insere a la fin du bloc presets: du YAML timeline
    const editor = document.getElementById('timeline-editor');
    let yaml = editor.value;
    const lines = yaml.split('\n');

    // Trouve la fin du bloc presets:
    let presetsStart = -1;
    for (let i = 0; i < lines.length; i++) {
        if (/^presets:\s*/.test(lines[i])) { presetsStart = i; break; }
    }

    if (presetsStart < 0) {
        // Pas de cle de premier niveau presets:, on insere en debut de fichier
        lines.unshift('presets:', ...block.split('\n'));
    } else {
        // Trouve la fin du bloc presets (prochaine cle de premier niveau)
        let presetsEnd = lines.length;
        for (let i = presetsStart + 1; i < lines.length; i++) {
            if (/^\S/.test(lines[i]) && !lines[i].startsWith('#') && lines[i].trim() !== '') {
                presetsEnd = i;
                break;
            }
        }
        // Insere avant presetsEnd (c.-a-d. a la fin du bloc presets)
        const blockLines = block.split('\n');
        lines.splice(presetsEnd, 0, ...blockLines);
    }

    editor.value = lines.join('\n');
    currentTimeline = editor.value;
    updateBackdrop('timeline-editor', 'timeline-backdrop');
    debounceSaveTimeline();

    // Bascule le preset de config.yaml vers le nouveau mode
    selectTimelinePreset(key);

    closeTlNewPresetModal();
    showToast(`Le mode de planification « ${name} » a ete cree avec succes`, 'success');
}

/**
 * Construit un bloc de texte YAML de preset vierge
 */
function buildEmptyPresetBlock(key, name, desc) {
    return [
        `  ${key}:`,
        `    name: "${name}"`,
        `    description: "${desc || ''}"`,
        `    default:`,
        `      collect: true`,
        `      analyze: false`,
        `      ai_mode: follow_report`,
        `      push: false`,
        `      report_mode: current`,
        `      once:`,
        `        analyze: false`,
        `        push: false`,
        `    periods: {}`,
        `    day_plans:`,
        `      all_day:`,
        `        periods: []`,
        `    week_map:`,
        `      1: all_day`,
        `      2: all_day`,
        `      3: all_day`,
        `      4: all_day`,
        `      5: all_day`,
        `      6: all_day`,
        `      7: all_day`,
        ``
    ].join('\n');
}

/**
 * Construit un bloc de texte YAML de preset a partir d'une configuration existante
 */
function buildPresetYamlBlock(key, cfg) {
    const obj = { [key]: cfg };
    let dumped = jsyaml.dump(obj, { indent: 2, lineWidth: -1, quotingType: '"', forceQuotes: false });
    // js-yaml serialise les cles numeriques de week_map en chaines entre guillemets ("1".."7"),
    // or le scheduler backend lit week_map avec isoweekday() en entier ; des cles chaines feraient echouer la validation au demarrage et empecheraient l'execution.
    // On retire ici les guillemets des cles purement numeriques, pour rester coherent avec les modeles ecrits a la main (1: all_day) et les cles entieres attendues par le backend.
    dumped = dumped.replace(/^(\s*)"(\d+)":/gm, '$1$2:');
    return dumped.split('\n').map(l => l ? '  ' + l : l).join('\n');
}

// ── Fenetre : ajout de plage horaire ──

let _tlNewPeriodTarget = '';

window.openTlNewPeriodModal = function(presetName) {
    _tlNewPeriodTarget = presetName;
    document.getElementById('tl-new-period-key').value = '';
    document.getElementById('tl-new-period-name').value = '';
    document.getElementById('tl-new-period-start').value = '09:00';
    document.getElementById('tl-new-period-end').value = '11:00';
    document.getElementById('tl-new-period-modal').classList.remove('hidden');
}

window.closeTlNewPeriodModal = function() {
    document.getElementById('tl-new-period-modal').classList.add('hidden');
}

window.confirmTlNewPeriod = function() {
    const key = document.getElementById('tl-new-period-key').value.trim();
    const name = document.getElementById('tl-new-period-name').value.trim();
    const start = document.getElementById('tl-new-period-start').value;
    const end = document.getElementById('tl-new-period-end').value;

    if (!key) { showToast("Veuillez saisir l'identifiant de la plage horaire (key)", 'error'); return; }
    if (!/^[a-zA-Z_][a-zA-Z0-9_]*$/.test(key)) { showToast('key Seuls lettres, chiffres et underscores sont acceptes', 'error'); return; }
    if (!name) { showToast('Veuillez saisir le nom affiche', 'error'); return; }
    if (!start || !end) { showToast('Veuillez definir les heures de debut et de fin', 'error'); return; }
    if (start === end) { showToast('Les heures de debut et de fin ne peuvent pas etre identiques', 'error'); return; }

    const data = parseTimelineData();
    const presetCfg = getPresetConfig(data, _tlNewPeriodTarget);
    if (presetCfg?.periods?.[key]) { showToast(`La plage horaire « ${key} » existe deja`, 'error'); return; }

    const editor = document.getElementById('timeline-editor');
    const lines = editor.value.split('\n');

    const sectionInfo = findPresetSection(lines, _tlNewPeriodTarget);
    if (!sectionInfo) { showToast('Section de configuration du preset introuvable', 'error'); return; }

    const periodsLine = findChildKey(lines, sectionInfo.start, sectionInfo.end, sectionInfo.indent, 'periods');
    if (periodsLine < 0) { showToast('Section de configuration periods introuvable', 'error'); return; }

    const periodsIndent = lines[periodsLine].search(/\S/);
    const periodsContent = lines[periodsLine].trim();
    const childIndent = periodsIndent + 2;
    const periodIndent = childIndent + 2;
    const indent = ' '.repeat(childIndent);
    const subIndent = ' '.repeat(periodIndent);

    const newPeriodLines = [
        `${indent}${key}:`,
        `${subIndent}name: "${name}"`,
        `${subIndent}start: "${start}"`,
        `${subIndent}end: "${end}"`,
        `${subIndent}collect: true`,
        `${subIndent}analyze: false`,
        `${subIndent}push: true`,
        `${subIndent}report_mode: current`
    ];

    if (periodsContent === 'periods: {}' || periodsContent === 'periods:{}') {
        lines[periodsLine] = ' '.repeat(periodsIndent) + 'periods:';
        lines.splice(periodsLine + 1, 0, ...newPeriodLines);
    } else {
        const periodsEnd = findBlockEnd(lines, periodsLine, periodsIndent, sectionInfo.end);
        lines.splice(periodsEnd, 0, ...newPeriodLines);
    }

    editor.value = lines.join('\n');
    currentTimeline = editor.value;
    updateBackdrop('timeline-editor', 'timeline-backdrop');
    debounceSaveTimeline();

    closeTlNewPeriodModal();
    syncTimelineToUI();
    showToast(`La plage horaire « ${name} » a ete ajoutee avec succes`, 'success');
}

// ── Supprimer la plage horaire ──

window.deleteTlPeriod = function(presetName, periodKey) {
    const data = parseTimelineData();
    const config = getPresetConfig(data, presetName);
    if (!config) return;

    const refs = [];
    const dayPlans = config.day_plans || {};
    Object.entries(dayPlans).forEach(([planName, plan]) => {
        if ((plan.periods || []).includes(periodKey)) refs.push(planName);
    });

    const periodName = config.periods?.[periodKey]?.name || periodKey;
    let msg = `Voulez-vous vraiment supprimer la plage horaire « ${periodName} » ?`;
    if (refs.length > 0) {
        msg += `\n\n⚠️ Cette plage est referencee par les plans journaliers suivants ; les references seront aussi retirees :\n${refs.map(r => '  • ' + r).join('\n')}`;
    }
    if (!confirm(msg)) return;

    const editor = document.getElementById('timeline-editor');
    const lines = editor.value.split('\n');

    const sectionInfo = findPresetSection(lines, presetName);
    if (!sectionInfo) return;

    const periodsLine = findChildKey(lines, sectionInfo.start, sectionInfo.end, sectionInfo.indent, 'periods');
    if (periodsLine >= 0) {
        const periodsIndent = lines[periodsLine].search(/\S/);
        const periodsEnd = findBlockEnd(lines, periodsLine, periodsIndent, sectionInfo.end);
        const periodLine = findChildKey(lines, periodsLine, periodsEnd, periodsIndent, periodKey);
        if (periodLine >= 0) {
            const periodIndent = lines[periodLine].search(/\S/);
            const periodEnd = findBlockEnd(lines, periodLine, periodIndent, periodsEnd);
            lines.splice(periodLine, periodEnd - periodLine);
        }
    }

    if (refs.length > 0) {
        const updatedSection = findPresetSection(lines, presetName);
        if (updatedSection) removePeriodFromDayPlans(lines, updatedSection, periodKey);
    }

    editor.value = lines.join('\n');
    currentTimeline = editor.value;
    updateBackdrop('timeline-editor', 'timeline-backdrop');
    debounceSaveTimeline();
    syncTimelineToUI();
    showToast(`La plage horaire « ${periodName} » a ete supprimee`, 'success');
}

// ── Copier la plage horaire ──

window.duplicateTlPeriod = function(presetName, periodKey) {
    const data = parseTimelineData();
    const config = getPresetConfig(data, presetName);
    if (!config?.periods?.[periodKey]) return;

    let newKey = periodKey + '_copy';
    let i = 2;
    while (config.periods[newKey]) { newKey = periodKey + '_copy' + i; i++; }

    const src = config.periods[periodKey];
    const editor = document.getElementById('timeline-editor');
    const lines = editor.value.split('\n');

    const sectionInfo = findPresetSection(lines, presetName);
    if (!sectionInfo) return;

    const periodsLine = findChildKey(lines, sectionInfo.start, sectionInfo.end, sectionInfo.indent, 'periods');
    if (periodsLine < 0) return;

    const periodsIndent = lines[periodsLine].search(/\S/);
    const periodsEnd = findBlockEnd(lines, periodsLine, periodsIndent, sectionInfo.end);
    const srcLine = findChildKey(lines, periodsLine, periodsEnd, periodsIndent, periodKey);
    if (srcLine < 0) return;

    const srcIndent = lines[srcLine].search(/\S/);
    const srcEnd = findBlockEnd(lines, srcLine, srcIndent, periodsEnd);

    const copiedLines = [];
    for (let li = srcLine; li < srcEnd; li++) {
        let line = lines[li];
        if (li === srcLine) {
            line = line.replace(periodKey, newKey);
        }
        copiedLines.push(line);
    }
    for (let li = 0; li < copiedLines.length; li++) {
        const m = copiedLines[li].match(/^(\s*name:\s*).+$/);
        if (m) {
            const newName = (src.name || periodKey) + ' (copie)';
            copiedLines[li] = `${m[1]}"${newName}"`;
            break;
        }
    }

    lines.splice(srcEnd, 0, ...copiedLines);
    editor.value = lines.join('\n');
    currentTimeline = editor.value;
    updateBackdrop('timeline-editor', 'timeline-backdrop');
    debounceSaveTimeline();
    syncTimelineToUI();
    showToast(`Copie en « ${newKey} »`, 'success');
}

// ── Supprime un mode de planification ──

const PROTECTED_PRESETS = ['morning_evening', 'always_on', 'office_hours', 'night_owl'];

window.deleteTlPreset = function(presetName) {
    if (PROTECTED_PRESETS.includes(presetName)) {
        showToast('Les presets integres ne peuvent pas etre supprimes ; utilisez la fonction de copie', 'warning');
        return;
    }
    if (presetName === 'custom') {
        showToast('Le mode custom ne peut pas etre supprime', 'warning');
        return;
    }

    const data = parseTimelineData();
    const cfg = data?.presets?.[presetName];
    const displayName = cfg?.name || presetName;

    if (!confirm(`Voulez-vous vraiment supprimer le mode de planification « ${displayName} » ?\nCette action est irreversible.`)) return;

    const editor = document.getElementById('timeline-editor');
    const lines = editor.value.split('\n');

    const sectionInfo = findPresetSection(lines, presetName);
    if (!sectionInfo) return;

    lines.splice(sectionInfo.start, sectionInfo.end - sectionInfo.start);

    editor.value = lines.join('\n');
    currentTimeline = editor.value;
    updateBackdrop('timeline-editor', 'timeline-backdrop');
    debounceSaveTimeline();

    if (getActivePreset() === presetName) {
        selectTimelinePreset('morning_evening');
    } else {
        syncTimelineToUI();
    }
    showToast(`Le mode de planification « ${displayName} » a ete supprimee`, 'success');
}

// ── Copie un mode de planification ──

window.duplicateTlPreset = function(presetName) {
    const data = parseTimelineData();
    const src = getPresetConfig(data, presetName);
    if (!src) return;

    openTlNewPresetModal();
    const origName = src.name || presetName;
    document.getElementById('tl-new-preset-key').value = presetName + '_copy';
    document.getElementById('tl-new-preset-name').value = origName + ' (copie)';
    document.getElementById('tl-new-preset-desc').value = src.description || '';
    document.getElementById('tl-new-preset-template').value = presetName;
}

// ── Ajout d'un plan journalier ──

window.addTlDayPlan = function(presetName) {
    const planKey = prompt("Saisissez l'identifiant du plan journalier (key), ex. holiday :");
    if (!planKey) return;
    if (!/^[a-zA-Z_][a-zA-Z0-9_]*$/.test(planKey)) {
        showToast('key Seuls lettres, chiffres et underscores sont acceptes', 'error');
        return;
    }

    const data = parseTimelineData();
    const config = getPresetConfig(data, presetName);
    if (config?.day_plans?.[planKey]) {
        showToast(`Le plan journalier « ${planKey} » existe deja`, 'error');
        return;
    }

    const editor = document.getElementById('timeline-editor');
    const lines = editor.value.split('\n');

    const sectionInfo = findPresetSection(lines, presetName);
    if (!sectionInfo) return;

    const dayPlansLine = findChildKey(lines, sectionInfo.start, sectionInfo.end, sectionInfo.indent, 'day_plans');
    if (dayPlansLine < 0) return;

    const dpIndent = lines[dayPlansLine].search(/\S/);
    const dpEnd = findBlockEnd(lines, dayPlansLine, dpIndent, sectionInfo.end);

    const indent = ' '.repeat(dpIndent + 2);
    const subIndent = ' '.repeat(dpIndent + 4);

    lines.splice(dpEnd, 0,
        `${indent}${planKey}:`,
        `${subIndent}periods: []`
    );

    editor.value = lines.join('\n');
    currentTimeline = editor.value;
    updateBackdrop('timeline-editor', 'timeline-backdrop');
    debounceSaveTimeline();
    syncTimelineToUI();
    showToast(`Le plan journalier « ${planKey} » a ete ajoute`, 'success');
}

// ── Supprimer le plan journalier ──

window.deleteTlDayPlan = function(presetName, planKey) {
    const data = parseTimelineData();
    const config = getPresetConfig(data, presetName);
    if (!config) return;

    const weekMap = config.week_map || {};
    const refs = [];
    for (let d = 1; d <= 7; d++) {
        const v = weekMap[d] || weekMap[String(d)];
        if (v === planKey) refs.push(DAY_NAMES[d - 1]);
    }

    if (refs.length > 0) {
        showToast(`Suppression impossible : « ${planKey} » est actuellement utilise par ${refs.join(', ')}. Modifiez d'abord la correspondance hebdomadaire.`, 'error');
        return;
    }

    if (!confirm(`Voulez-vous vraiment supprimer le plan journalier « ${planKey} » ?`)) return;

    const editor = document.getElementById('timeline-editor');
    const lines = editor.value.split('\n');

    const sectionInfo = findPresetSection(lines, presetName);
    if (!sectionInfo) return;

    const dayPlansLine = findChildKey(lines, sectionInfo.start, sectionInfo.end, sectionInfo.indent, 'day_plans');
    if (dayPlansLine < 0) return;

    const dpIndent = lines[dayPlansLine].search(/\S/);
    const dpEnd = findBlockEnd(lines, dayPlansLine, dpIndent, sectionInfo.end);
    const planLine = findChildKey(lines, dayPlansLine, dpEnd, dpIndent, planKey);
    if (planLine < 0) return;

    const planIndent = lines[planLine].search(/\S/);
    const planEnd = findBlockEnd(lines, planLine, planIndent, dpEnd);

    lines.splice(planLine, planEnd - planLine);

    editor.value = lines.join('\n');
    currentTimeline = editor.value;
    updateBackdrop('timeline-editor', 'timeline-backdrop');
    debounceSaveTimeline();
    syncTimelineToUI();
    showToast(`Le plan journalier « ${planKey} » a ete supprimee`, 'success');
}

// ── Ajout / retrait d'une reference de plage dans un plan journalier ──

window.addPeriodToDayPlan = function(presetName, planKey, periodKey) {
    const editor = document.getElementById('timeline-editor');
    const lines = editor.value.split('\n');

    const sectionInfo = findPresetSection(lines, presetName);
    if (!sectionInfo) return;

    const dayPlansLine = findChildKey(lines, sectionInfo.start, sectionInfo.end, sectionInfo.indent, 'day_plans');
    if (dayPlansLine < 0) return;

    const dpIndent = lines[dayPlansLine].search(/\S/);
    const dpEnd = findBlockEnd(lines, dayPlansLine, dpIndent, sectionInfo.end);
    const planLine = findChildKey(lines, dayPlansLine, dpEnd, dpIndent, planKey);
    if (planLine < 0) return;

    const planIndent = lines[planLine].search(/\S/);
    const planEnd = findBlockEnd(lines, planLine, planIndent, dpEnd);
    const periodsLine = findChildKey(lines, planLine, planEnd, planIndent, 'periods');
    if (periodsLine < 0) return;

    const periodsContent = lines[periodsLine].trim();

    if (periodsContent === 'periods: []' || periodsContent === 'periods:[]') {
        const pIndent = ' '.repeat(lines[periodsLine].search(/\S/));
        lines[periodsLine] = `${pIndent}periods:`;
        lines.splice(periodsLine + 1, 0, `${pIndent}  - ${periodKey}`);
    } else {
        const inlineMatch = lines[periodsLine].match(/^(\s*periods:\s*)\[([^\]]*)\]/);
        if (inlineMatch) {
            const existing = inlineMatch[2].split(',').map(s => s.trim()).filter(Boolean);
            // Conserve un style de guillemets coherent
            const hasQuotes = existing.length > 0 && existing[0].startsWith('"');
            existing.push(hasQuotes ? `"${periodKey}"` : periodKey);
            lines[periodsLine] = `${inlineMatch[1]}[${existing.join(', ')}]`;
        } else {
            const pIndent = ' '.repeat(lines[periodsLine].search(/\S/) + 2);
            const listEnd = findBlockEnd(lines, periodsLine, lines[periodsLine].search(/\S/), planEnd);
            lines.splice(listEnd, 0, `${pIndent}- ${periodKey}`);
        }
    }

    editor.value = lines.join('\n');
    currentTimeline = editor.value;
    updateBackdrop('timeline-editor', 'timeline-backdrop');
    debounceSaveTimeline();
    syncTimelineToUI();
}

window.removePeriodFromDayPlanUI = function(presetName, planKey, periodKey) {
    const editor = document.getElementById('timeline-editor');
    const lines = editor.value.split('\n');

    const sectionInfo = findPresetSection(lines, presetName);
    if (!sectionInfo) return;

    removePeriodFromDayPlanInLines(lines, sectionInfo, planKey, periodKey);

    editor.value = lines.join('\n');
    currentTimeline = editor.value;
    updateBackdrop('timeline-editor', 'timeline-backdrop');
    debounceSaveTimeline();
    syncTimelineToUI();
}

// ── Operations rapides de correspondance hebdomadaire ──

window.tlWeekMapQuick = function(presetName, mode) {
    const data = parseTimelineData();
    const config = getPresetConfig(data, presetName);
    if (!config) return;

    const dayPlanKeys = Object.keys(config.day_plans || {});
    if (dayPlanKeys.length === 0) { showToast('Aucun plan journalier disponible', 'error'); return; }

    let mapping = {};

    if (mode === 'all_same') {
        const plan = dayPlanKeys[0];
        for (let d = 1; d <= 7; d++) mapping[d] = plan;
    } else if (mode === 'weekday_same') {
        const plan = dayPlanKeys[0];
        for (let d = 1; d <= 5; d++) mapping[d] = plan;
        const wm = config.week_map || {};
        mapping[6] = wm[6] || wm['6'] || plan;
        mapping[7] = wm[7] || wm['7'] || plan;
    } else if (mode === 'weekday_weekend') {
        if (dayPlanKeys.length < 2) { showToast('Il faut au moins deux plans journaliers pour separer jours ouvres et week-end', 'warning'); return; }
        const wd = dayPlanKeys[0];
        const we = dayPlanKeys[1];
        for (let d = 1; d <= 5; d++) mapping[d] = wd;
        mapping[6] = we;
        mapping[7] = we;
    }

    for (let d = 1; d <= 7; d++) {
        if (mapping[d]) onTlWeekMap(presetName, d, mapping[d]);
    }
    showToast('Correspondance hebdomadaire mise a jour', 'success');
}

// ── Fonctions utilitaires ──

/**
 * Localise les lignes de debut et de fin de la section de configuration du preset
 */
function findPresetSection(lines, presetName) {
    const isCustom = presetName === 'custom';
    let start = -1;
    let indent = 0;

    if (isCustom) {
        for (let i = 0; i < lines.length; i++) {
            if (/^custom:\s*/.test(lines[i])) { start = i; indent = 0; break; }
        }
    } else {
        let inPresets = false;
        for (let i = 0; i < lines.length; i++) {
            const line = lines[i];
            if (/^presets:\s*/.test(line)) { inPresets = true; continue; }
            if (inPresets && /^\S/.test(line) && !line.startsWith('#') && line.trim() !== '') break;
            if (inPresets) {
                const m = line.match(/^(\s+)(\S+):\s*/);
                if (m && m[2] === presetName) { start = i; indent = m[1].length; break; }
            }
        }
    }

    if (start < 0) return null;

    let end = lines.length;
    for (let i = start + 1; i < lines.length; i++) {
        const line = lines[i];
        if (line.trim() === '' || line.trim().startsWith('#')) continue;
        const curIndent = line.search(/\S/);
        if (curIndent <= indent) { end = i; break; }
    }

    return { start, end, indent };
}

/**
 * Retire en masse les references a une plage donnee dans day_plans
 */
function removePeriodFromDayPlans(lines, sectionInfo, periodKey) {
    const dayPlansLine = findChildKey(lines, sectionInfo.start, sectionInfo.end, sectionInfo.indent, 'day_plans');
    if (dayPlansLine < 0) return;

    const dpIndent = lines[dayPlansLine].search(/\S/);
    const sectionEnd = findBlockEnd(lines, sectionInfo.start, sectionInfo.indent, lines.length);
    const dpEnd = findBlockEnd(lines, dayPlansLine, dpIndent, sectionEnd);

    for (let i = dayPlansLine + 1; i < dpEnd; i++) {
        const line = lines[i];
        if (line.trim() === '' || line.trim().startsWith('#')) continue;
        const listMatch = line.match(/^(\s*)-\s*(\S+)\s*$/);
        if (listMatch && listMatch[2] === periodKey) {
            lines.splice(i, 1);
            i--;
            continue;
        }
        const inlineMatch = line.match(/^(\s*periods:\s*)\[([^\]]*)\]/);
        if (inlineMatch) {
            const items = inlineMatch[2].split(',').map(s => s.trim()).filter(s => {
                const bare = s.replace(/^["']|["']$/g, '');
                return bare && bare !== periodKey;
            });
            lines[i] = items.length > 0
                ? `${inlineMatch[1]}[${items.join(', ')}]`
                : `${inlineMatch[1]}[]`;
        }
    }
}

/**
 * Retire une reference de plage unique d'un plan journalier donne
 */
function removePeriodFromDayPlanInLines(lines, sectionInfo, planKey, periodKey) {
    const dayPlansLine = findChildKey(lines, sectionInfo.start, sectionInfo.end, sectionInfo.indent, 'day_plans');
    if (dayPlansLine < 0) return;

    const dpIndent = lines[dayPlansLine].search(/\S/);
    const dpEnd = findBlockEnd(lines, dayPlansLine, dpIndent, sectionInfo.end);
    const planLine = findChildKey(lines, dayPlansLine, dpEnd, dpIndent, planKey);
    if (planLine < 0) return;

    const planIndent = lines[planLine].search(/\S/);
    const planEnd = findBlockEnd(lines, planLine, planIndent, dpEnd);
    const periodsLine = findChildKey(lines, planLine, planEnd, planIndent, 'periods');
    if (periodsLine < 0) return;

    const inlineMatch = lines[periodsLine].match(/^(\s*periods:\s*)\[([^\]]*)\]/);
    if (inlineMatch) {
        const items = inlineMatch[2].split(',').map(s => s.trim()).filter(s => {
            const bare = s.replace(/^["']|["']$/g, '');
            return bare && bare !== periodKey;
        });
        lines[periodsLine] = items.length > 0
            ? `${inlineMatch[1]}[${items.join(', ')}]`
            : `${inlineMatch[1]}[]`;
        return;
    }

    const pEnd = findBlockEnd(lines, periodsLine, lines[periodsLine].search(/\S/), planEnd);
    for (let i = periodsLine + 1; i < pEnd; i++) {
        const m = lines[i].match(/^(\s*)-\s*(\S+)\s*$/);
        if (m && m[2] === periodKey) {
            lines.splice(i, 1);
            return;
        }
    }
}

// ==========================================
// 15. Fonctions d'amelioration ulterieures
// ==========================================

// ── 1.3 / 3A.4 Edition en ligne (double-clic pour editer le texte)──

/**
 * Edition en ligne du nom / de la description de la carte de preset
 */
window.tlInlineEdit = function(el, presetName, field, currentValue) {
    if (el.querySelector('input')) return;

    const original = currentValue;
    const isName = field === 'name';
    const input = document.createElement('input');
    input.type = 'text';
    input.value = original;
    input.className = `tl-inline-input ${isName ? 'text-sm font-bold' : 'text-[10px]'}`;
    input.style.width = '100%';

    el.textContent = '';
    el.appendChild(input);
    input.focus();
    input.select();

    const commit = () => {
        const newVal = input.value.trim();
        if (newVal && newVal !== original) {
            updatePresetMeta(presetName, field, newVal);
        }
        syncTimelineToUI();
    };

    input.addEventListener('blur', commit);
    input.addEventListener('keydown', e => {
        if (e.key === 'Enter') { e.preventDefault(); input.blur(); }
        if (e.key === 'Escape') { el.textContent = original; }
    });
}

/**
 * Met a jour les champs name / description de premier niveau du preset
 */
function updatePresetMeta(presetName, field, value) {
    const editor = document.getElementById('timeline-editor');
    const lines = editor.value.split('\n');

    const sectionInfo = findPresetSection(lines, presetName);
    if (!sectionInfo) return;

    const lineIdx = findChildKey(lines, sectionInfo.start, sectionInfo.end, sectionInfo.indent, field);
    if (lineIdx >= 0) {
        replaceLineValue(lines, lineIdx, value);
    } else {
        const indent = ' '.repeat(sectionInfo.indent + 2);
        lines.splice(sectionInfo.start + 1, 0, `${indent}${field}: "${value}"`);
    }

    editor.value = lines.join('\n');
    currentTimeline = editor.value;
    updateBackdrop('timeline-editor', 'timeline-backdrop');
    debounceSaveTimeline();
}

/**
 * Edition en ligne du nom de la plage horaire
 */
window.tlInlineEditPeriod = function(el, presetName, periodKey, currentValue) {
    if (el.querySelector('input')) return;

    const original = currentValue;
    const input = document.createElement('input');
    input.type = 'text';
    input.value = original;
    input.className = 'tl-inline-input text-sm font-bold';
    input.style.width = Math.max(80, original.length * 14) + 'px';

    el.textContent = '';
    el.appendChild(input);
    input.focus();
    input.select();

    const commit = () => {
        const newVal = input.value.trim();
        if (newVal && newVal !== original) {
            updateTimelineField(presetName, periodKey, 'name', newVal);
        }
        syncTimelineToUI();
    };

    input.addEventListener('blur', commit);
    input.addEventListener('keydown', e => {
        if (e.key === 'Enter') { e.preventDefault(); input.blur(); }
        if (e.key === 'Escape') { el.textContent = original; }
    });
}

// ── 2.2 Clic sur une zone vide de la vue hebdomadaire → affiche le nom du plan journalier ──

window.onTlBarClick = function(event, presetName, dayNum) {
    if (event.target.closest('.tl-period-block')) return;

    const data = parseTimelineData();
    const config = getPresetConfig(data, presetName);
    if (!config) return;

    const weekMap = config.week_map || {};
    const planKey = weekMap[dayNum] || weekMap[String(dayNum)] || '(non defini)';

    hideTlTooltip();
    const el = document.createElement('div');
    el.className = 'tl-tooltip';
    el.innerHTML = `<div style="font-weight:700;margin-bottom:2px">${DAY_NAMES[dayNum - 1]}</div>
        <div style="font-size:11px;color:#9ca3af">Plan journalier : <strong style="color:#374151">${planKey}</strong></div>
        <div style="font-size:10px;color:#9ca3af;margin-top:4px">Utilise la configuration default</div>`;

    document.body.appendChild(el);
    tlTooltipEl = el;

    const rect = event.currentTarget.getBoundingClientRect();
    const x = event.clientX;
    el.style.left = (x - el.offsetWidth / 2) + 'px';
    el.style.top = (rect.top - el.offsetHeight - 8) + 'px';

    const elRect = el.getBoundingClientRect();
    if (elRect.left < 4) el.style.left = '4px';
    if (elRect.right > window.innerWidth - 4) el.style.left = (window.innerWidth - el.offsetWidth - 4) + 'px';
    if (elRect.top < 4) el.style.top = (rect.bottom + 8) + 'px';

    setTimeout(() => { if (tlTooltipEl === el) hideTlTooltip(); }, 2000);
}

// ── 3B.5 Tri par glisser-deposer des etiquettes de plan journalier ──

/**
 * Initialise SortableJS sur le conteneur d'etiquettes de plage du plan journalier
 */
function initDayPlanSortable(presetName) {
    document.querySelectorAll('.tl-dayplan-sortable').forEach(container => {
        const planKey = container.dataset.planKey;
        if (!planKey) return;

        new Sortable(container, {
            animation: 150,
            ghostClass: 'tl-tag-ghost',
            dragClass: 'tl-tag-drag',
            draggable: '.tl-period-tag',
            filter: '.tl-add-period-select, .tl-tag-remove',
            preventOnFilter: false,
            onEnd: function() {
                const items = [];
                container.querySelectorAll('.tl-period-tag').forEach(tag => {
                    const key = tag.dataset.periodKey;
                    if (key) items.push(key);
                });
                reorderDayPlanPeriods(presetName, planKey, items);
            }
        });
    });
}

/**
 * Reordonne les plages (periods) dans un plan journalier
 */
function reorderDayPlanPeriods(presetName, planKey, orderedKeys) {
    const editor = document.getElementById('timeline-editor');
    const lines = editor.value.split('\n');

    const sectionInfo = findPresetSection(lines, presetName);
    if (!sectionInfo) return;

    const dayPlansLine = findChildKey(lines, sectionInfo.start, sectionInfo.end, sectionInfo.indent, 'day_plans');
    if (dayPlansLine < 0) return;

    const dpIndent = lines[dayPlansLine].search(/\S/);
    const dpEnd = findBlockEnd(lines, dayPlansLine, dpIndent, sectionInfo.end);
    const planLine = findChildKey(lines, dayPlansLine, dpEnd, dpIndent, planKey);
    if (planLine < 0) return;

    const planIndent = lines[planLine].search(/\S/);
    const planEnd = findBlockEnd(lines, planLine, planIndent, dpEnd);
    const periodsLine = findChildKey(lines, planLine, planEnd, planIndent, 'periods');
    if (periodsLine < 0) return;

    const inlineMatch = lines[periodsLine].match(/^(\s*periods:\s*)\[([^\]]*)\]/);
    if (inlineMatch) {
        lines[periodsLine] = `${inlineMatch[1]}[${orderedKeys.join(', ')}]`;
    } else {
        const pIndent = lines[periodsLine].search(/\S/);
        const pEnd = findBlockEnd(lines, periodsLine, pIndent, planEnd);
        lines.splice(periodsLine + 1, pEnd - periodsLine - 1);
        const itemIndent = ' '.repeat(pIndent + 2);
        const newItems = orderedKeys.map(k => `${itemIndent}- ${k}`);
        lines.splice(periodsLine + 1, 0, ...newItems);
    }

    editor.value = lines.join('\n');
    currentTimeline = editor.value;
    updateBackdrop('timeline-editor', 'timeline-backdrop');
    debounceSaveTimeline();

    clearTimeout(window._tlRenderTimer);
    window._tlRenderTimer = setTimeout(() => syncTimelineToUI(), 500);
}

// ==========================================
// Replier / deplier la barre laterale de soutien
// ==========================================
function toggleSupportSidebar() {
    const wrap = document.querySelector('.support-sidebar-wrap');
    const btn = document.getElementById('sidebar-toggle-btn');
    const isCollapsed = wrap.classList.toggle('collapsed');
    btn.classList.toggle('is-collapsed', isCollapsed);
    btn.title = isCollapsed ? 'Deplier la barre laterale' : 'Replier la barre laterale';
}
