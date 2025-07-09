export const encryptData = (data) => {
  return btoa(data); // Base64 as placeholder encryption
};

export const checkLLMRisk = async (data) => {
  // Placeholder for OpenRouter MiniMax M1 API
  const risk = Math.random();
  return risk > 0.7 ? 'Unauthorized LLM access detected' : 'Secure';
};
