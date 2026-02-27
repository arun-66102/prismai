// Admin Dashboard Logic

let currentEditUserId = null;

document.addEventListener('DOMContentLoaded', () => {
    // Check if user is logged in
    const token = localStorage.getItem('prism_access_token');
    if (!token) {
        window.location.href = '/';
        return;
    }

    // We rely on the API to kick them out if they aren't an admin,
    // but let's try to fetch right away.
    fetchStats();
    fetchUsers();
});

async function fetchStats() {
    try {
        const stats = await apiGet('/admin/stats');

        document.getElementById('statUsers').textContent = stats.total_users;
        document.getElementById('statBlogs').textContent = stats.total_blogs;
        document.getElementById('statVideos').textContent = stats.total_videos;
        document.getElementById('statImages').textContent = stats.total_images;

    } catch (error) {
        console.error("Failed to load stats:", error);
        // If 403, it means they aren't an admin, kick them back
        if (error.message.includes("403")) {
            showToast("Access Denied: Admin privileges required.", "error");
            setTimeout(() => { window.location.href = '/' }, 1500);
        }
    }
}

async function fetchUsers() {
    const tableBody = document.getElementById('usersTableBody');
    tableBody.innerHTML = '<tr><td colspan="5" class="loading-cell">Loading accounts from database...</td></tr>';

    try {
        const users = await apiGet('/admin/users');

        if (users.length === 0) {
            tableBody.innerHTML = '<tr><td colspan="5" class="loading-cell">No users found.</td></tr>';
            return;
        }

        tableBody.innerHTML = '';
        users.forEach(user => {
            const tr = document.createElement('tr');

            // Format dates safely
            const joinedDate = new Date(user.created_at).toLocaleDateString();
            const lastLogin = user.last_login ? new Date(user.last_login).toLocaleString() : 'Never';

            tr.innerHTML = `
                <td>
                    <div class="user-cell">
                        <span class="user-name">${user.name}</span>
                        <span class="user-email">${user.email}</span>
                    </div>
                </td>
                <td>
                    <div class="user-cell" style="gap: 0.4rem; flex-direction: row; align-items: center;">
                        <span class="role-badge ${user.role}">${user.role}</span>
                        <span class="tier-badge ${user.tier}">${user.tier}</span>
                        <span class="status-badge ${user.is_active ? 'active' : 'suspended'}">${user.is_active ? 'Active' : 'Suspended'}</span>
                    </div>
                </td>
                <td class="text-muted-cell">${joinedDate}</td>
                <td class="text-muted-cell">${lastLogin}</td>
                <td>
                    <button class="btn-small" onclick="openTierModal('${user.id}', '${user.name}', '${user.tier}', '${user.role}', ${user.is_active})">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M12 20h9"></path>
                            <path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"></path>
                        </svg>
                        Manage
                    </button>
                </td>
            `;
            tableBody.appendChild(tr);
        });

    } catch (error) {
        console.error("Failed to load users:", error);
        tableBody.innerHTML = '<tr><td colspan="5" class="loading-cell">Failed to load users.</td></tr>';
    }
}

// Modal Logic
function openTierModal(userId, userName, currentTier, currentRole, currentStatus) {
    currentEditUserId = userId;

    document.getElementById('modalUserName').textContent = userName;
    document.getElementById('newTierSelect').value = currentTier;
    document.getElementById('newRoleSelect').value = currentRole;
    document.getElementById('newStatusSelect').value = currentStatus.toString();

    document.getElementById('tierModal').classList.add('show');
}

function closeTierModal() {
    document.getElementById('tierModal').classList.remove('show');
    currentEditUserId = null;
}

document.getElementById('saveTierBtn').addEventListener('click', async () => {
    if (!currentEditUserId) return;

    const newTier = document.getElementById('newTierSelect').value;
    const newRole = document.getElementById('newRoleSelect').value;
    const newStatus = document.getElementById('newStatusSelect').value === "true";
    const btn = document.getElementById('saveTierBtn');

    btn.textContent = 'Saving...';
    btn.disabled = true;

    try {
        const token = localStorage.getItem('prism_access_token');
        const response = await fetch(`http://127.0.0.1:8000/admin/users/${currentEditUserId}`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({ tier: newTier, role: newRole, is_active: newStatus })
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || "Failed to update account");
        }

        showToast("Account updated successfully", "success");
        closeTierModal();

        // Refresh users list gently
        fetchUsers();

    } catch (error) {
        console.error("Error updating account:", error);
        showToast(error.message, "error");
    } finally {
        btn.textContent = 'Confirm Update';
        btn.disabled = false;
    }
});

// Since the new app.js might not have apiGet exposed if we refactor, let's make sure we have a local fetch wrapper just in case 
// (assuming app.js exposes `apiGet` and `showToast` globally from window)

async function apiGet(endpoint) {
    const token = localStorage.getItem('prism_access_token');

    const response = await fetch(`http://127.0.0.1:8000${endpoint}`, {
        method: 'GET',
        headers: {
            'Authorization': `Bearer ${token}`
        }
    });

    if (response.status === 401) {
        // Let app.js try to handle refresh, but if it fails we just throw
        throw new Error("401 Unauthorized");
    }

    if (response.status === 403) {
        throw new Error("403 Forbidden");
    }

    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `Request failed with status ${response.status}`);
    }

    return response.json();
}
