"use strict";
//database-backed store for recording metadata and results, using IndexedDB
const DB_NAME = "went-respiratory";
const DB_VERSION = 2;
const STORE = "records";
export const MAX_RECORDINGS = 30;
let dbPromise = null;

export function isStoreSupported() { return typeof indexedDB !== "undefined"; }
function openDb() {
  if (!isStoreSupported()) return Promise.reject(new Error("This browser does not support IndexedDB"));
  if (dbPromise) return dbPromise;
  dbPromise = new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);
    request.onupgradeneeded = () => { const db = request.result; if (!db.objectStoreNames.contains(STORE)) db.createObjectStore(STORE, { keyPath: "id" }); };
    request.onsuccess = () => { const db = request.result; db.onversionchange = () => { db.close(); dbPromise = null; }; resolve(db); };
    request.onerror = () => { dbPromise = null; reject(request.error || new Error("Unable to open the local record store")); };
    request.onblocked = () => reject(new Error("The record store is busy in another page; close it and retry"));
  });
  return dbPromise;
}
function requestValue(request) { return new Promise((resolve, reject) => { request.onsuccess = () => resolve(request.result); request.onerror = () => reject(request.error || new Error("Record request failed")); }); }
async function runTransaction(mode, operation) {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const transaction = db.transaction(STORE, mode); const store = transaction.objectStore(STORE); let result;
    try { result = operation(store); } catch (error) { transaction.abort(); reject(error); return; }
    transaction.oncomplete = async () => { try { resolve(await result); } catch (error) { reject(error); } };
    transaction.onerror = () => reject(transaction.error || new Error("Record transaction failed"));
    transaction.onabort = () => reject(transaction.error || new Error("Record transaction aborted"));
  });
}
export function makeRecordingId() { if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") return crypto.randomUUID(); return `went-${Date.now()}-${Math.random().toString(16).slice(2, 10)}`; }
export function cloneForStorage(value, seen = new WeakMap()) {
  if (value == null || typeof value !== "object") return value;
  if (value instanceof Blob || value instanceof ArrayBuffer || value instanceof Date) return value;
  if (ArrayBuffer.isView(value)) return value.slice ? value.slice() : value;
  if (seen.has(value)) return seen.get(value);
  if (Array.isArray(value)) { const copy = []; seen.set(value, copy); value.forEach((item) => copy.push(cloneForStorage(item, seen))); return copy; }
  const copy = {}; seen.set(value, copy); for (const [key, item] of Object.entries(value)) copy[key] = cloneForStorage(item, seen); return copy;
}
export async function probeRecordStore() { const id = `probe-${Date.now()}`; await runTransaction("readwrite", (store) => { store.put({ id, createdAt: new Date().toISOString(), probe: true }); store.delete(id); }); }
export async function putRecording(record) { const next = cloneForStorage({ ...record, id: record.id || makeRecordingId(), createdAt: record.createdAt || new Date().toISOString() }); await runTransaction("readwrite", (store) => store.put(next)); await pruneToLimit(); return next; }
export async function getRecording(id) { return runTransaction("readonly", (store) => requestValue(store.get(id))); }
export async function listRecordings() { const rows = await runTransaction("readonly", (store) => requestValue(store.getAll())); return rows.filter((row) => !row.probe).sort((a, b) => String(b.createdAt).localeCompare(String(a.createdAt))); }
export async function updateRecording(id, patch) { const existing = await getRecording(id); if (!existing) return null; const next = cloneForStorage({ ...existing, ...patch, id }); await runTransaction("readwrite", (store) => store.put(next)); return next; }
export async function deleteRecording(id) { await runTransaction("readwrite", (store) => store.delete(id)); }
async function pruneToLimit() { const rows = await listRecordings(); if (rows.length <= MAX_RECORDINGS) return; await runTransaction("readwrite", (store) => rows.slice(MAX_RECORDINGS).forEach((row) => store.delete(row.id))); }
export async function estimateUsage() { if (!navigator.storage?.estimate) return null; try { const { usage = 0, quota = 0 } = await navigator.storage.estimate(); return { usage, quota }; } catch { return null; } }
export const saveRecord = putRecording;
export const updateRecord = updateRecording;
export const listRecords = listRecordings;
