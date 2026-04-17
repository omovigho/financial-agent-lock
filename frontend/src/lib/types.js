// Type definitions as JSDoc comments for IDE support

/**
 * @typedef {Object} User
 * @property {number} id
 * @property {string} email
 * @property {string} name
 * @property {string} auth0_id
 * @property {string} role
 */

/**
 * @typedef {Object} Token
 * @property {string} token_id
 * @property {string} scope
 * @property {string} system
 * @property {string} expires_at
 * @property {string} created_at
 */

/**
 * @typedef {Object} Policy
 * @property {number} id
 * @property {string} name
 * @property {string} action
 * @property {string} system
 * @property {string} rule
 * @property {string} [description]
 */

/**
 * @typedef {Object} Approval
 * @property {number} id
 * @property {string} action
 * @property {string} system
 * @property {'pending' | 'approved' | 'denied' | 'expired'} status
 * @property {string} created_at
 * @property {string} expires_at
 * @property {Record<string, any>} request_data
 * @property {string} [approved_by]
 * @property {string} [reason]
 */

/**
 * @typedef {Object} Transaction
 * @property {number} id
 * @property {string} date
 * @property {string} description
 * @property {number} amount
 * @property {string} category
 */

/**
 * @typedef {Object} AuditLog
 * @property {number} id
 * @property {number} user_id
 * @property {string} action
 * @property {string} system
 * @property {string} timestamp
 * @property {Record<string, any>} details
 */

/**
 * @typedef {Object} InteractionStream
 * @property {string} id
 * @property {string} user_email
 * @property {string} action
 * @property {string} system
 * @property {'low' | 'medium' | 'high'} risk_level
 * @property {'success' | 'pending' | 'blocked'} status
 * @property {string} timestamp
 * @property {Record<string, any>} metadata
 */

/**
 * @typedef {Object} AgentResponse
 * @property {string} status
 * @property {string} decision
 * @property {Record<string, any>} requirements
 */

export {}
