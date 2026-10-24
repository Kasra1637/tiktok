import { useEffect, useRef, useState } from "react";
import { api, getErrorMessage } from "../lib/api";

// Copy belongs to the editor. This hook owns only the current app's unshown
// messages; old persisted preset lists never become generated copy.
export function useOpeningMessages({ profileId, text, onText }) {
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState(null);
  const batch = useRef({ remaining: [], shown: [] });
  const request = useRef(null);
  const currentText = useRef(text);
  currentText.current = text;

  useEffect(() => {
    batch.current = { remaining: [], shown: [] };
    request.current = null;
    setGenerating(false);
    setError(null);
    return () => { request.current = null; };
  }, [profileId]);

  const updateText = (value) => {
    currentText.current = value;
    onText(value);
  };

  const surprise = async () => {
    if (request.current) return false;
    setError(null);
    // A manual edit may equal an unused suggestion. Never reapply that line.
    batch.current.remaining = batch.current.remaining.filter((v) => v !== currentText.current);
    if (batch.current.remaining.length) {
      updateText(batch.current.remaining.shift());
      return true;
    }
    const token = {};
    request.current = token;
    const before = currentText.current;
    setGenerating(true);
    try {
      const previous = [...new Set([...batch.current.shown, before].filter(Boolean))].slice(-20);
      const result = await api.generateOpeningMessages(profileId, previous);
      if (request.current !== token) return false;
      const messages = result?.messages;
      if (!Array.isArray(messages) || messages.length !== 20 ||
          messages.some((v) => typeof v !== "string" || !v.trim() || previous.includes(v.trim())) ||
          new Set(messages.map((v) => v.trim().toLowerCase())).size !== 20) {
        throw new Error("Could not generate 20 distinct opening messages. Try Surprise me again.");
      }
      batch.current = { remaining: messages.map((v) => v.trim()), shown: messages.map((v) => v.trim()) };
      // Don't overwrite a manual edit made during the network request.
      if (currentText.current !== before) return false;
      updateText(batch.current.remaining.shift());
      return true;
    } catch (e) {
      if (request.current === token) setError(getErrorMessage(e));
      return false;
    } finally {
      if (request.current === token) {
        request.current = null;
        setGenerating(false);
      }
    }
  };
  return { generating, error, surprise, updateText };
}
