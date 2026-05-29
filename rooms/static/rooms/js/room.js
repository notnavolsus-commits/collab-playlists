document.addEventListener('DOMContentLoaded', function () {

    // ========== ИНИЦИАЛИЗАЦИЯ ПЕРЕМЕННЫХ ==========

    const slug = window.location.pathname.split('/').filter(p => p).pop();
    const isCreator = window.isCreator || false;
    let isBroadcasting = false;
    let currentBroadcastTrackId = null;
    let syncInterval = null;

    // ========== НАСТРОЙКА WEBSOCKET СОЕДИНЕНИЯ ==========

    const socket = new WebSocket(`ws://127.0.0.1:8000/ws/rooms/${slug}/`);

    // События: соединение установлено, ошибка, соединение закрыто

    socket.onopen = function (event) {
        console.log('Websocket подключён!');
    };

    socket.onerror = function (error) {
        console.log('Ошибка:', error);
    };

    socket.onclose = function (event) {
        console.log('Соединение закрыто');
        if (syncInterval) clearInterval(syncInterval);
    };

    // ========== DOM ЭЛЕМЕНТЫ ==========

    let tracks = document.querySelector(`.tracks-container`);
    const trackCounter = document.querySelector('.tracks-counter');
    const broadcastStatusPar = document.querySelector('div.broadcast-status');
    const voteButtons = document.querySelectorAll('.track-vote-button');
    const start_broadcast_buttons = document.querySelectorAll('.start-broadcast-btn');
    const delete_track_buttons = document.querySelectorAll('.delete-track-btn');
    const stopBtn = document.querySelector('.stop-broadcast-btn')

    // ========== ОБРАБОТЧИК КНОПКИ "ОСТАНОВИТЬ ЭФИР" ==========
    if (stopBtn) {
        stopBtn.addEventListener('click', () => {
            socket.send(JSON.stringify({action: 'stop_broadcast', room_slug: slug}));

            if (isCreator) {
                if (syncInterval) clearInterval(syncInterval);
                isBroadcasting = false;
                currentBroadcastTrackId = null;
                stopBtn.style.display = 'none';
            }
            if (broadcastStatusPar) broadcastStatusPar.style.display = 'none';
        });
    }

    // ========== УДАЛЕНИЕ ТРЕКА (AJAX) ==========
    for (let button of delete_track_buttons) {
            button.addEventListener('click', () => {
                let trackId = button.dataset.trackId;
                let roomSlug = slug;
                let csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');

                if (!confirm('Удалить трек?')) return;

                fetch(`/rooms/${roomSlug}/delete_track/${trackId}/`, {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': csrfToken,
                    },
                })
                    .then(response => {
                            if (!response.ok) {
                                throw new Error(`HTTP server error! Status ${response.status}`);
                            }
                            return response.json();
                        }
                    )
                    .then(data => {
                        if (data.success) {
                            const track = document.querySelector(`div.track-container[data-track-id="${trackId}"]`);
                            if (track) {
                                track.remove();
                            }
                            if (trackCounter) {
                                let text = trackCounter.innerText;
                                let match = text.match(/\d+/);
                                if (match) {
                                    let currentCount = parseInt(match[0]);
                                    trackCounter.innerText = text.replace(currentCount, currentCount - 1);

                                }
                            }
                        } else alert(data.error);
                    })
                    .catch(error => {
                        console.error('Ошибка: ', error);
                        alert('Не удалось удалить трек');
                    });
            });
        }

    // ========== ЗАПУСК ПРЯМОГО ЭФИРА (ТОЛЬКО ДЛЯ СОЗДАТЕЛЯ) ==========
    if (isCreator) {
            for (let button of start_broadcast_buttons) {
                button.addEventListener('click', () => {
                    if (isBroadcasting) {
                        alert('Эфир уже идёт. Остановите его перед запуском нового.')
                        return;
                    }
                    let trackId = button.dataset.trackId;
                    socket.send(JSON.stringify({action: 'start_broadcast', track_id: trackId}));
                    if (stopBtn) stopBtn.style.display = 'inline-block';

                    currentBroadcastTrackId = trackId;
                    isBroadcasting = true;

                    let trackContainer = document.querySelector(`div.track-container[data-track-id="${trackId}"]`)
                    let trackName = trackContainer.querySelector('h2.track-name').innerText;
                    if (broadcastStatusPar) {
                        let broadcastNameSpan = broadcastStatusPar.querySelector('span#broadcast-track-name');
                        if (broadcastNameSpan) broadcastNameSpan.innerText = trackName;
                        broadcastStatusPar.style.display = 'inline-block';
                    }

                    if (syncInterval) clearInterval(syncInterval);

                    syncInterval = setInterval(() => {
                        if (isBroadcasting && currentBroadcastTrackId) {
                            const trackPlayer = document.querySelector(`div.track-container[data-track-id="${currentBroadcastTrackId}"] > audio`);
                            if (trackPlayer && !trackPlayer.paused) {
                                socket.send(JSON.stringify({
                                    action: 'sync_broadcast',
                                    track_id: currentBroadcastTrackId,
                                    current_time: trackPlayer.currentTime
                                }));
                            }
                        }
                    }, 5000);
                });
            }
        }

    // ========== ОБРАБОТЧИК КНОПОК ГОЛОСОВАНИЯ ==========
    for (let button of voteButtons) {
        button.addEventListener('click', () => {
            const trackId = button.dataset.trackId
            socket.send(JSON.stringify({action: 'vote', room_track_id: trackId}));
        });
    }

    // ========== ОБРАБОТКА ВХОДЯЩИХ WEBSOCKET СООБЩЕНИЙ ==========

    socket.onmessage = function (event) {
        const data = JSON.parse(event.data);
        // ----- ОБРАБОТКА ГОЛОСОВАНИЯ -----
        if (data.action === 'voted' || data.action === 'unvoted') {
            let room_track_id = data['room_track_id'];
            let new_votes_count = data['new_votes_count'];
            let new_order = data['new_order'];
            let vote_counter = document.querySelector(`#votes-${room_track_id}`);
            if (vote_counter) {
                vote_counter.innerText = `${new_votes_count}`;
            }
            new_order.forEach(id => {
                let child = document.querySelector(`div.track-container[data-track-id="${id}"]`);
                tracks.appendChild(child);
            });
        }

        // ----- ОБРАБОТКА УДАЛЕНИЯ ТРЕКА -----
        else if (data.action === 'delete_track') {
            const trackId = data.track_id;
            const trackElement = document.querySelector(`.track-container[data-track-id="${trackId}"]`);
            if (trackElement) {
                trackElement.remove();
                if (trackCounter) {
                    let text = trackCounter.innerText;
                    let match = text.match(/\d+/);
                    if (match) {
                        let currentCount = parseInt(match[0]);
                        trackCounter.innerText = text.replace(currentCount, currentCount - 1);
                    }
                }
            }
        }

        // ----- ОБРАБОТКА ЗАПУСКА ЭФИРА (ДЛЯ УЧАСТНИКОВ) -----
        else if (data.action === 'start_broadcast') {
            let trackId = data.track_id;
            let trackContainer = document.querySelector(`div.track-container[data-track-id="${trackId}"]`)
            let trackPlayer = trackContainer.querySelector('audio');
            let trackName = trackContainer.querySelector('h2.track-name').innerText;
            if (broadcastStatusPar) {
                let broadcastNameSpan = broadcastStatusPar.querySelector('span#broadcast-track-name');
                if (broadcastNameSpan) broadcastNameSpan.innerText = trackName;
                broadcastStatusPar.style.display = 'inline-block';
            }
            if (trackPlayer) {
                trackPlayer.currentTime = 0;
                trackPlayer.play().catch(e => console.log('Ошибка произведения: ', e));
            }

        }

        // ----- ОБРАБОТКА СИНХРОНИЗАЦИИ ЭФИРА -----
        else if (data.action === 'sync_broadcast') {
            let trackId = data.track_id;
            let serverTime = data.current_time;
            let trackPlayer = document.querySelector(`div.track-container[data-track-id="${trackId}"] > audio`);
            if (trackPlayer && Math.abs(trackPlayer.currentTime - serverTime) > 0.5) {
                trackPlayer.currentTime = serverTime;
            }
        }

        // ----- ОБРАБОТКА ОСТАНОВКИ ЭФИРА -----
        else if (data.action === 'stop_broadcast') {
            document.querySelectorAll('div.track-container > audio').forEach(trackPlayer => {
                trackPlayer.pause();
                trackPlayer.currentTime = 0;
                if (broadcastStatusPar) broadcastStatusPar.style.display = 'none';
            });

            if (isCreator) {
                if (syncInterval) clearInterval(syncInterval);
                isBroadcasting = false;
                currentBroadcastTrackId = null;
                if (stopBtn) stopBtn.style.display = 'none';
            }
        }
    }

    // ========== ОБРАБОТКА ЗАКРЫТИЯ СТРАНИЦЫ ==========
    window.addEventListener('beforeunload', () => {
        if (isBroadcasting && socket.readyState === WebSocket.OPEN) {
            socket.send(JSON.stringify({action: 'stop_broadcast', room_slug: slug}));
        }
    });
});
