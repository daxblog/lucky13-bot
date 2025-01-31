// Zorg ervoor dat de socket verbinding wordt opgebouwd zodra de pagina wordt geladen
const socket = io.connect("https://lucky13-bot-8b1fa5884ddc.herokuapp.com/");

// UI elementen
let saldoElement = document.getElementById("balance");
let activeTradesContainer = document.getElementById("trades-list");
let chartContainer = document.getElementById("winningsChart");  // Grafiek container aangepast
let errorMessageContainer = document.getElementById("errorMessages");
let botStatusIndicator = document.getElementById("bot-status");

// Chart.js instance
let balanceChart = null;

// Update de balans op de pagina
function updateBalance(data) {
    if (saldoElement) {
        saldoElement.innerText = `Saldo: ${data.balance.toFixed(2)} USDT`;
    }
}

// Update de lijst van actieve trades
function updateActiveTrades(data) {
    if (activeTradesContainer) {
        activeTradesContainer.innerHTML = ""; // Clear bestaande trades

        data.trades.forEach(trade => {
            const tradeElement = document.createElement("div");
            tradeElement.className = `trade-item ${trade.current_profit > 0 ? 'success' : 'failure'}`;
            tradeElement.innerHTML = `
                <span>Trade: ${trade.symbol}</span>
                <span>Status: ${trade.current_profit > 0 ? 'Profit' : 'Loss'}</span>
                <span>Winst/Verlies: ${trade.current_profit > 0 ? '+' : ''}${(trade.current_profit * 100).toFixed(2)}%</span>
            `;
            activeTradesContainer.appendChild(tradeElement);
        });
    }
}

// Foutmeldingen tonen
function showErrorMessages(messages) {
    if (errorMessageContainer) {
        errorMessageContainer.innerHTML = ""; // Clear bestaande berichten

        messages.forEach(message => {
            const messageElement = document.createElement("div");
            messageElement.className = "error-message";
            messageElement.innerText = message;
            errorMessageContainer.appendChild(messageElement);
        });
    }
}

// Grafiek bijwerken voor winsten en stortingen
function updateGraph(winnings, deposits) {
    if (chartContainer) {
        if (balanceChart) {
            // Update de bestaande grafiek als deze er al is
            balanceChart.data.datasets[0].data = [winnings, deposits];
            balanceChart.update();
        } else {
            // Maak een nieuwe grafiek aan
            const ctx = chartContainer.getContext("2d");
            const chartData = {
                labels: ['Winsten', 'Stortingen'],  // Labels voor de grafiek
                datasets: [{
                    label: 'USDT',
                    data: [winnings, deposits],  // Gegevens voor winsten en stortingen
                    backgroundColor: ['#28a745', '#dc3545'],
                    borderColor: ['#28a745', '#dc3545'],
                    borderWidth: 1
                }]
            };

            balanceChart = new Chart(ctx, {
                type: 'bar',
                data: chartData,
                options: {
                    responsive: true,
                    scales: {
                        y: {
                            beginAtZero: true
                        }
                    }
                });
            });
        }
    }
}

// Bot status bijwerken
function updateBotStatus(isRunning) {
    if (botStatusIndicator) {
        botStatusIndicator.innerText = isRunning ? "✅ Bot is actief" : "❌ Bot is gestopt";
        botStatusIndicator.style.color = isRunning ? "green" : "red";
    }
}

// Socket.io event handlers
socket.on('update_balance', function(data) {
    console.log("Balance update ontvangen:", data);  // Debugging log
    updateBalance(data);
});

socket.on('update_trades', function(data) {
    console.log("Active trades update ontvangen:", data);  // Debugging log
    updateActiveTrades(data);
});

socket.on('update_graph', function(data) {
    console.log("Graph update ontvangen:", data);  // Debugging log
    updateGraph(data.winnings, data.deposits);  // Update de grafiek met winsten en stortingen
});

socket.on('error_messages', function(data) {
    console.log("Foutmelding ontvangen:", data);  // Debugging log
    showErrorMessages(data);
});

// Bot status event
socket.on('bot_status', function(data) {
    console.log("Bot status ontvangen:", data);  // Debugging log
    if (data && data.hasOwnProperty('running')) {
        updateBotStatus(data.running);
    } else {
        console.error("Ongeldige botstatus data:", data);
    }
});

// Exporteer de grafiek naar een CSV bestand
function exportChartToCSV() {
    if (!balanceChart) {
        alert("Geen gegevens beschikbaar om te exporteren.");
        return;
    }

    const labels = balanceChart.data.labels;
    const values = balanceChart.data.datasets[0].data;

    if (!labels || labels.length === 0 || !values || values.length === 0) {
        alert("Geen gegevens beschikbaar voor export.");
        return;
    }

    let csvContent = "Label,Value\n";
    labels.forEach((label, index) => {
        csvContent += `${label},${values[index]}\n`;
    });

    const blob = new Blob([csvContent], { type: 'text/csv' });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = `chart_${new Date().toLocaleDateString()}.csv`;
    link.click();
}

// Button voor het exporteren van de grafiek (Als je deze functionaliteit wilt behouden)
const exportButton = document.getElementById("exportChart");
if (exportButton) {
    exportButton.addEventListener("click", exportChartToCSV);
}

// Instellingen tabbladen wisselen
document.addEventListener("DOMContentLoaded", function () {
    // Tabbladen wisselen
    const homeTab = document.getElementById("home-tab");
    const settingsTab = document.getElementById("settings-tab");

    if (homeTab) {
        homeTab.addEventListener("click", function() {
            document.getElementById("home-content").style.display = "block";
            document.getElementById("settings-content").style.display = "none";
        });
    }

    if (settingsTab) {
        settingsTab.addEventListener("click", function() {
            document.getElementById("home-content").style.display = "none";
            document.getElementById("settings-content").style.display = "block";
            loadSettings();
        });
    }

    // Instellingen opslaan
    const settingsForm = document.getElementById("settings-form");
    if (settingsForm) {
        settingsForm.addEventListener("submit", function(event) {
            event.preventDefault();

            const settings = {
                trade_percentage: parseFloat(document.getElementById("trade-percentage").value),
                stop_loss_percentage: parseFloat(document.getElementById("stop-loss-percentage").value),
                take_profit_percentage: parseFloat(document.getElementById("take-profit-percentage").value)
            };

            fetch("/api/settings", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify(settings)
            })
            .then(response => response.json())
            .then(data => {
                alert(data.message);
            })
            .catch(error => {
                console.error("Fout bij opslaan van instellingen:", error);
                alert("Kon de instellingen niet opslaan.");
            });
        });
    }

    // Instellingen laden bij het openen van de instellingen tab
    function loadSettings() {
        fetch("/api/settings")
            .then(response => response.json())
            .then(settings => {
                document.getElementById("trade-percentage").value = settings.trade_percentage || 0.02;
                document.getElementById("stop-loss-percentage").value = settings.stop_loss_percentage || 0.03;
                document.getElementById("take-profit-percentage").value = settings.take_profit_percentage || 0.05;
            })
            .catch(error => {
                console.error("Fout bij laden van instellingen:", error);
                alert("Er is een fout opgetreden bij het laden van de instellingen.");
            });
    }
});