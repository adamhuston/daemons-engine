/**
 * Settings Manager
 * 
 * Persists app settings (last opened folder, window state) to a JSON file
 * in the user's app data directory.
 */

import { app } from 'electron';
import fs from 'fs';
import path from 'path';

interface WindowState {
  width: number;
  height: number;
  x?: number;
  y?: number;
  isMaximized?: boolean;
}

interface AppSettings {
  lastOpenedFolder?: string;
  windowState?: WindowState;
  recentFolders?: string[];
}

const SETTINGS_FILE = path.join(app.getPath('userData'), 'settings.json');

let settings: AppSettings = {};

/**
 * Load settings from disk
 */
export function loadSettings(): AppSettings {
  try {
    if (fs.existsSync(SETTINGS_FILE)) {
      const data = fs.readFileSync(SETTINGS_FILE, 'utf-8');
      settings = JSON.parse(data);
    }
  } catch (error) {
    console.error('Failed to load settings:', error);
    settings = {};
  }
  return settings;
}

/**
 * Save settings to disk
 */
export function saveSettings(): void {
  try {
    const dir = path.dirname(SETTINGS_FILE);
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }
    fs.writeFileSync(SETTINGS_FILE, JSON.stringify(settings, null, 2));
  } catch (error) {
    console.error('Failed to save settings:', error);
  }
}

/**
 * Get a setting value
 */
export function getSetting<K extends keyof AppSettings>(key: K): AppSettings[K] {
  return settings[key];
}

/**
 * Set a setting value and persist
 */
export function setSetting<K extends keyof AppSettings>(key: K, value: AppSettings[K]): void {
  settings[key] = value;
  saveSettings();
}

/**
 * Get window state with defaults
 */
export function getWindowState(): WindowState {
  return settings.windowState ?? { width: 1200, height: 800 };
}

/**
 * Save window state
 */
export function saveWindowState(state: WindowState): void {
  settings.windowState = state;
  saveSettings();
}

/**
 * Add folder to recent list
 */
export function addRecentFolder(folderPath: string): void {
  const recent = settings.recentFolders ?? [];
  // Remove if already exists, then add to front
  const filtered = recent.filter(f => f !== folderPath);
  filtered.unshift(folderPath);
  // Keep only last 10
  settings.recentFolders = filtered.slice(0, 10);
  settings.lastOpenedFolder = folderPath;
  saveSettings();
}
