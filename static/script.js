// Auto-hide alerts after 5 seconds
document.addEventListener('DOMContentLoaded', function() {
    setTimeout(function() {
        const alerts = document.querySelectorAll('.alert');
        alerts.forEach(function(alert) {
            const bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        });
    }, 5000);
});

// Confirm delete
function confirmDelete(expenseId) {
    return confirm('Are you sure you want to delete this expense?');
}

// Format currency
function formatCurrency(amount) {
    return 'KSH ' + parseFloat(amount).toFixed(2);
}

// Live search/filter for expenses
function filterExpenses() {
    const input = document.getElementById('searchInput');
    if (!input) return;
    
    const filter = input.value.toUpperCase();
    const table = document.getElementById('expenseTable');
    if (!table) return;
    
    const rows = table.getElementsByTagName('tr');
    
    for (let i = 1; i < rows.length; i++) {
        const cells = rows[i].getElementsByTagName('td');
        let found = false;
        for (let j = 0; j < cells.length - 1; j++) {
            const txtValue = cells[j].textContent || cells[j].innerText;
            if (txtValue.toUpperCase().indexOf(filter) > -1) {
                found = true;
                break;
            }
        }
        rows[i].style.display = found ? '' : 'none';
    }
}

// Debug function
console.log('💰 Expense Tracker loaded successfully!');

// PWA Support - Service Worker Registration (for future PWA)
if ('serviceWorker' in navigator) {
    // Uncomment when ready for PWA
    // navigator.serviceWorker.register('/static/service-worker.js')
    //     .then(function(registration) {
    //         console.log('Service Worker registered successfully');
    //     })
    //     .catch(function(error) {
    //         console.log('Service Worker registration failed:', error);
    //     });
}