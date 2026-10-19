/**
 * JBSN AI OS Gemini proxy adapter.
 *
 * Add the small doPost routing block below to the EXISTING deployed UCX Apps Script:
 *
 *   if (data && data.action === 'aios_business_plan') {
 *     return ContentService.createTextOutput(
 *       JSON.stringify(JBSN_AIOS_GEMINI_PROXY_(data))
 *     ).setMimeType(ContentService.MimeType.JSON);
 *   }
 *
 * Insert that block after parsing data and before the existing call to
 * JBSN_UCX_MESSAGE(data). Then add the function below and redeploy the existing
 * web app as a new version. Existing WhatsApp/customer requests remain unchanged.
 *
 * Set Script Property JBSN_AIOS_PROXY_TOKEN to a long random secret. The matching
 * Render variable is JBSN_GEMINI_PROXY_TOKEN. Never commit either token or the
 * GEMINI_API_KEY. This adapter reads the already-configured GEMINI_API_KEY from
 * Apps Script Script Properties and does not create customer/lead/conversation rows.
 */
function JBSN_AIOS_GEMINI_PROXY_(data) {
  var props = PropertiesService.getScriptProperties();
  var expected = String(props.getProperty('JBSN_AIOS_PROXY_TOKEN') || '');
  var supplied = String((data && data.token) || '');
  if (!expected || !supplied || expected.length !== supplied.length) return {ok:false,error:'unauthorized'};
  var mismatch = 0;
  for (var i = 0; i < expected.length; i++) mismatch |= expected.charCodeAt(i) ^ supplied.charCodeAt(i);
  if (mismatch !== 0) return {ok:false,error:'unauthorized'};

  var objective = String((data && data.objective) || '').trim().slice(0, 4000);
  var business = String((data && data.business) || 'JBSN Creative').trim().slice(0, 200);
  if (!objective) return {ok:false,error:'objective_required'};
  var key = String(props.getProperty('GEMINI_API_KEY') || '');
  if (!key) return {ok:false,error:'gemini_not_configured'};
  var model = String(props.getProperty('JBSN_GEMINI_MODEL') || 'gemini-2.5-flash');
  var prompt = [
    'You are the planning engine for JBSN AI OS. Create a practical, testable business plan.',
    'Do not claim to have executed actions. Identify assumptions, acceptance criteria, risks, approvals needed, and measurable next steps.',
    'Return only valid JSON with keys: summary, assumptions, steps, acceptance_criteria, risks, approvals_required.',
    'Business: ' + business,
    'Objective: ' + objective
  ].join('\\n');
  var response;
  try {
    response = UrlFetchApp.fetch(
      'https://generativelanguage.googleapis.com/v1beta/models/' + encodeURIComponent(model) +
      ':generateContent?key=' + encodeURIComponent(key),
      {method:'post',contentType:'application/json',
       payload:JSON.stringify({contents:[{role:'user',parts:[{text:prompt}]}],
         generationConfig:{temperature:0.2,responseMimeType:'application/json'}}),
       muteHttpExceptions:true}
    );
  } catch (err) { return {ok:false,error:'gemini_connection_failed'}; }
  if (response.getResponseCode() < 200 || response.getResponseCode() >= 300)
    return {ok:false,error:'gemini_provider_http_' + response.getResponseCode()};
  var outer;
  try { outer = JSON.parse(response.getContentText()); }
  catch (err) { return {ok:false,error:'gemini_invalid_response'}; }
  var text = outer && outer.candidates && outer.candidates[0] && outer.candidates[0].content &&
    outer.candidates[0].content.parts && outer.candidates[0].content.parts[0] &&
    outer.candidates[0].content.parts[0].text;
  var plan;
  try { plan = JSON.parse(text); }
  catch (err) { return {ok:false,error:'gemini_invalid_plan_json'}; }
  if (!plan || typeof plan !== 'object' || !Array.isArray(plan.steps) ||
      !('summary' in plan) || !('acceptance_criteria' in plan) ||
      !('risks' in plan) || !('approvals_required' in plan))
    return {ok:false,error:'gemini_plan_schema_invalid'};
  return {ok:true,provider:'google_gemini',model:model,plan:plan};
}
