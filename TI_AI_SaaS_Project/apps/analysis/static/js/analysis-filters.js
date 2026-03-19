/**
 * Analysis Results Filter JavaScript
 * Handles real-time filtering of analysis results with debouncing
 * Matches styling and approach from dashboard.js
 */

(function() {
    'use strict';

    // Debounce timer for filter changes
    let filterTimeout = null;
    const FILTER_DEBOUNCE_DELAY = 500; // 500ms debounce delay

    /**
     * Get CSRF token from meta tag
     * @returns {string|null} CSRF token
     */
    function getCsrfToken() {
        const tokenMeta = document.querySelector('meta[name="csrf-token"]');
        return tokenMeta ? tokenMeta.getAttribute('content') : null;
    }

    /**
     * Build query string from filter values
     * @returns {string} Query string
     */
    function buildFilterQueryString() {
        const params = new URLSearchParams();
        
        // Get filter values
        const category = document.getElementById('category-filter')?.value || '';
        const minScore = document.getElementById('min-score')?.value || '';
        const maxScore = document.getElementById('max-score')?.value || '';
        const minEducationScore = document.getElementById('min-education-score')?.value || '';
        const maxEducationScore = document.getElementById('max-education-score')?.value || '';
        const minSkillsScore = document.getElementById('min-skills-score')?.value || '';
        const maxSkillsScore = document.getElementById('max-skills-score')?.value || '';
        const minExperienceScore = document.getElementById('min-experience-score')?.value || '';
        const maxExperienceScore = document.getElementById('max-experience-score')?.value || '';

        // Add non-empty filters to params
        if (category) params.set('category', category);
        if (minScore) params.set('min_score', minScore);
        if (maxScore) params.set('max_score', maxScore);
        if (minEducationScore) params.set('min_education_score', minEducationScore);
        if (maxEducationScore) params.set('max_education_score', maxEducationScore);
        if (minSkillsScore) params.set('min_skills_score', minSkillsScore);
        if (maxSkillsScore) params.set('max_skills_score', maxSkillsScore);
        if (minExperienceScore) params.set('min_experience_score', minExperienceScore);
        if (maxExperienceScore) params.set('max_experience_score', maxExperienceScore);

        return params.toString();
    }

    /**
     * Apply filters by fetching new results
     */
    function applyFilters() {
        const queryString = buildFilterQueryString();
        const currentUrl = window.location.pathname;
        const newUrl = queryString ? `${currentUrl}?${queryString}` : currentUrl;

        // Use fetch to get new results without full page reload
        fetch(newUrl, {
            method: 'GET',
            headers: {
                'X-Requested-With': 'XMLHttpRequest'
            },
            credentials: 'include'
        })
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            return response.text();
        })
        .then(html => {
            // Parse the HTML response
            const parser = new DOMParser();
            const doc = parser.parseFromString(html, 'text/html');
            
            // Update filter controls section
            const oldFilterControls = document.querySelector('.filter-controls');
            const newFilterControls = doc.querySelector('.filter-controls');
            if (oldFilterControls && newFilterControls) {
                oldFilterControls.outerHTML = newFilterControls.outerHTML;
            }

            // Update results table
            const oldTable = document.querySelector('.overflow-x-auto');
            const newTable = doc.querySelector('.overflow-x-auto');
            if (oldTable && newTable) {
                oldTable.outerHTML = newTable.outerHTML;
            }

            // Update pagination
            const oldPagination = document.querySelector('[data-pagination-controls]');
            const newPagination = doc.querySelector('[data-pagination-controls]');
            if (oldPagination && newPagination) {
                oldPagination.outerHTML = newPagination.outerHTML;
            }

            // Re-attach event listeners to new filter controls
            attachFilterListeners();

            // Update URL without page reload
            const newFullUrl = queryString ? `${currentUrl}?${queryString}` : currentUrl;
            window.history.pushState({ path: newFullUrl }, '', newFullUrl);

            console.log('Filters applied successfully');
        })
        .catch(error => {
            console.error('Error applying filters:', error);
            // Fallback to full page reload
            window.location.href = newUrl;
        });
    }

    /**
     * Clear all filters
     */
    function clearFilters() {
        // Reset all filter inputs
        const categoryFilter = document.getElementById('category-filter');
        const minScore = document.getElementById('min-score');
        const maxScore = document.getElementById('max-score');
        const minEducationScore = document.getElementById('min-education-score');
        const maxEducationScore = document.getElementById('max-education-score');
        const minSkillsScore = document.getElementById('min-skills-score');
        const maxSkillsScore = document.getElementById('max-skills-score');
        const minExperienceScore = document.getElementById('min-experience-score');
        const maxExperienceScore = document.getElementById('max-experience-score');

        if (categoryFilter) categoryFilter.value = '';
        if (minScore) minScore.value = '';
        if (maxScore) maxScore.value = '';
        if (minEducationScore) minEducationScore.value = '';
        if (maxEducationScore) maxEducationScore.value = '';
        if (minSkillsScore) minSkillsScore.value = '';
        if (maxSkillsScore) maxSkillsScore.value = '';
        if (minExperienceScore) minExperienceScore.value = '';
        if (maxExperienceScore) maxExperienceScore.value = '';

        // Apply cleared filters
        applyFilters();
    }

    /**
     * Handle filter input change with debouncing
     * @param {Event} event - Change event
     */
    function handleFilterChange(event) {
        const target = event.target;
        console.log('Filter changed:', target.id, 'value:', target.value);

        // Clear existing timeout
        if (filterTimeout) {
            clearTimeout(filterTimeout);
        }

        // Set new timeout for debounced filter application
        filterTimeout = setTimeout(() => {
            console.log('Applying filters after debounce');
            applyFilters();
        }, FILTER_DEBOUNCE_DELAY);
    }

    /**
     * Attach event listeners to filter controls
     */
    function attachFilterListeners() {
        // Category filter (select)
        const categoryFilter = document.getElementById('category-filter');
        if (categoryFilter) {
            categoryFilter.addEventListener('change', handleFilterChange);
        }

        // Score filters (inputs) - all min/max pairs
        const scoreInputs = [
            'min-score',
            'max-score',
            'min-education-score',
            'max-education-score',
            'min-skills-score',
            'max-skills-score',
            'min-experience-score',
            'max-experience-score'
        ];

        scoreInputs.forEach(inputId => {
            const input = document.getElementById(inputId);
            if (input) {
                // Apply on input (for immediate feedback) with debouncing
                input.addEventListener('input', handleFilterChange);
                // Also apply on change (for select/blur events)
                input.addEventListener('change', handleFilterChange);
            }
        });

        // Clear filters button
        const clearButton = document.getElementById('clear-filters');
        if (clearButton) {
            clearButton.addEventListener('click', clearFilters);
        }
    }

    /**
     * Initialize filter functionality on page load
     */
    function initFilters() {
        console.log('Initializing analysis filters');
        attachFilterListeners();
    }

    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initFilters);
    } else {
        initFilters();
    }

    // Expose functions globally if needed
    window.AnalysisFilters = {
        applyFilters: applyFilters,
        clearFilters: clearFilters,
        initFilters: initFilters
    };

})();
