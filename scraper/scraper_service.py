"""Scraping service for Wildberries reports"""
import os
import logging
import shutil
import zipfile
from typing import Callable, Awaitable

from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError

logger = logging.getLogger(__name__)

# Callback type: accepts a stage number, returns True if update succeeded
StatusCallback = Callable[[int], Awaitable[bool]]


async def _notify(on_status: StatusCallback | None, stage: int) -> None:
    """Safely invoke the status callback, swallowing errors."""
    if on_status is None:
        return
    try:
        await on_status(stage)
    except Exception as e:
        logger.warning(f"⚠️  Status callback failed for stage {stage}: {e}")


def generate_unique_id(*numbers):
    """
    Generate unique ID based on passed numbers (up to 5).
    Uses hashing to minimize collisions.
    """
    if not numbers:
        return 0
    
    # Create string from all numbers
    combined = ''.join(str(n) for n in numbers)
    
    # Use built-in hash() and take absolute value
    # Add salt to reduce collisions
    hash_value = hash(combined + '_salt_' + str(sum(numbers)))
    
    # Take absolute value and limit size
    unique_value = abs(hash_value) % (10**9)  # Limit to 9 digits
    
    return unique_value


class WBScraperService:
    """Service for scraping data from Wildberries platform"""
    
    def __init__(self, page: Page, downloads_path: str):
        self._page = page
        self._downloads_path = downloads_path

    async def fake_compare_cards(
        self,
        items: list[int],
        on_status: StatusCallback | None = None,
    ):
        """
        Mock function to simulate card comparison through table.

        Status stages used: 1 -> 2 -> 3 -> 4
        """
        # --- Stage 1: Открываем страницу сравнения ---
        await _notify(on_status, 1)

        logger.info('🌐 Navigating to page...')
        await self._page.goto(
            'https://seller.wildberries.ru/platform-analytics/cards-comparison',
            wait_until='domcontentloaded'
        )
        logger.info(f'✅ Page loaded: {self._page.url}')
        
        # Wait for page to stabilize after navigation
        logger.info('⏳ Waiting for page to stabilize after navigation...')
        await self._page.wait_for_timeout(3000)
        try:
            await self._page.wait_for_load_state('networkidle', timeout=15000)
            logger.info('✅ Network idle after navigation')
        except PlaywrightTimeoutError:
            logger.warning('⚠️  Network idle timeout after navigation')
        
        # --- Stage 2: Вводим артикулы товаров ---
        await _notify(on_status, 2)

        logger.info(f'🔍 Starting fake_compare_cards for {len(items)} articles...')
        
        # Find div with class starting with Table__container
        logger.info('🔍 Looking for table container...')
        table_container = self._page.locator('[class^="Table__container"]').first
        await table_container.wait_for(state='visible', timeout=15000)
        await self._page.wait_for_timeout(1000)
        logger.info('✅ Table container found')
        
        # Find table inside container
        logger.info('🔍 Looking for table...')
        table = table_container.locator('table').first
        await table.wait_for(state='visible', timeout=15000)
        await self._page.wait_for_timeout(1000)
        logger.info('✅ Table found')

        # --- Stage 3: Проверяем добавленные карточки ---
        await _notify(on_status, 3)
        
        # Find tbody in table
        logger.info('🔍 Looking for tbody...')
        tbody = table.locator('tbody').first
        await tbody.wait_for(state='visible', timeout=15000)
        await self._page.wait_for_timeout(1000)
        logger.info('✅ tbody found')
        
        # Find first tbody element (first tr)
        logger.info('🔍 Looking for first tbody element...')
        first_row = tbody.locator('tr').first
        await first_row.wait_for(state='visible', timeout=15000)
        await self._page.wait_for_timeout(1000)
        logger.info('✅ First element found')
        
        # Click on first element
        logger.info('🖱️  Clicking first tbody element...')
        try:
            # First, try to ensure element is clickable by waiting for any potential overlays
            await self._page.wait_for_timeout(1000)
            
            # Try clicking with force to bypass actionability checks
            await first_row.click(force=True, timeout=15000)
            logger.info('✅ Click completed with force=True')
        except PlaywrightTimeoutError:
            logger.warning('⚠️  Normal click failed, trying JavaScript click...')
            # Fallback to JavaScript click if force click fails
            await first_row.evaluate('element => element.click()')
            logger.info('✅ Click completed via JavaScript')
        
        await self._page.wait_for_timeout(2000)

        # --- Stage 4: Запускаем сравнение карточек ---
        await _notify(on_status, 4)
        
        # Wait for data to load after click
        logger.info('⏳ Waiting for data to load...')
        try:
            # Wait for network activity to settle
            await self._page.wait_for_load_state('networkidle', timeout=20000)
            logger.info('✅ Network idle')
        except PlaywrightTimeoutError:
            logger.warning('⚠️  Network idle timeout, waiting additional time...')
            # If network doesn't become idle, wait at least some time
            await self._page.wait_for_timeout(5000)
        
        # Additional wait for UI to stabilize
        await self._page.wait_for_timeout(2000)
        logger.info('✅ Page stabilized after click')
        
        logger.info('✅ fake_compare_cards function completed successfully!')
        return True

    async def compare_cards(
        self,
        items: list[int],
        on_status: StatusCallback | None = None,
    ):
        """
        Compare product cards by article numbers.

        Status stages used: 1 -> 2 -> 3 -> 4
        """
        # --- Stage 1: Открываем страницу сравнения ---
        await _notify(on_status, 1)

        logger.info(f'🔍 Starting card comparison for {len(items)} articles...')

        logger.info('🌐 Navigating to page...')
        await self._page.goto(
            'https://seller.wildberries.ru/platform-analytics/cards-comparison',
            wait_until='domcontentloaded'
        )
        logger.info(f'✅ Page loaded: {self._page.url}')
        
        # Wait for page to stabilize after navigation
        logger.info('⏳ Waiting for page to stabilize after navigation...')
        await self._page.wait_for_timeout(3000)
        try:
            await self._page.wait_for_load_state('networkidle', timeout=15000)
            logger.info('✅ Network idle after navigation')
        except PlaywrightTimeoutError:
            logger.warning('⚠️  Network idle timeout after navigation')
        
        # Find and click create comparison button
        logger.info('🔍 Looking for create comparison button...')
        create_comparison_button = self._page.locator('[class^="Create-comparison-button"]').first
        await create_comparison_button.wait_for(state='visible', timeout=15000)
        await self._page.wait_for_timeout(1000)
        logger.info('✅ Create comparison button found')
        
        await create_comparison_button.click()
        await self._page.wait_for_timeout(1000)
        logger.info('🖱️  Clicked create comparison button')
        
        # Wait for form to fully load
        await self._page.wait_for_timeout(1000)

        # --- Stage 2: Вводим артикулы товаров ---
        await _notify(on_status, 2)
        
        # For each article
        for idx, article in enumerate(items):
            logger.info(f'📦 [{idx + 1}/{len(items)}] Processing article: {article}')
            
            # Find input field
            logger.info('  🔍 Looking for input field...')
            simple_input = self._page.locator('[class^="Simple-input"]').first
            await simple_input.wait_for(state='visible', timeout=15000)
            await self._page.wait_for_timeout(500)
            
            input_field = simple_input.locator('input').first
            await input_field.wait_for(state='visible', timeout=10000)
            await self._page.wait_for_timeout(500)
            logger.info('  ✅ Input field found')
            
            # Enter article
            logger.info(f'  ⌨️  Entering article: {article}')
            await input_field.fill(str(article))
            await self._page.wait_for_timeout(1000)
            
            # Press Enter
            logger.info('  ⌨️  Pressing Enter...')
            await input_field.press('Enter')
            logger.info('  ✅ Enter pressed')
            
            # Wait for results to load
            await self._page.wait_for_timeout(1000)
            
            # Find recommended cards container
            logger.info('  🔍 Looking for recommended cards container...')
            recommended_cards_list = self._page.locator('[class^="Recommended-cards__list"]').first
            await recommended_cards_list.wait_for(state='visible', timeout=15000)
            await self._page.wait_for_timeout(1000)
            logger.info('  ✅ Container found')

            # Verify correct article was added
            logger.info('  🔍 Verifying added article...')
            nm_cards = recommended_cards_list.locator('[class^="Nm-card__description"]')
            await nm_cards.last.wait_for(state='visible', timeout=15000)
            await self._page.wait_for_timeout(1000)
            
            # Get last element
            first_card = nm_cards.last
            
            # Find span with article text
            span_with_article = first_card.locator(f'span:has-text("{article}")').first
            
            # Check that span exists
            try:
                await span_with_article.wait_for(state='visible', timeout=10000)
                span_text = await span_with_article.inner_text()
                logger.info(f'  ✅ Article {article} confirmed (found text: "{span_text}")')
            except PlaywrightTimeoutError:
                # If span not found, raise error
                actual_text = await first_card.inner_text()
                error_msg = f'Error: Article {article} not found in last card. Card text: "{actual_text}"'
                logger.error(f'  ❌ {error_msg}')
                raise ValueError(error_msg)
            
            # After verifying article - find and click last control button
            logger.info('  🔍 Looking for card control buttons...')
            control_buttons = recommended_cards_list.locator('[class^="Nm-card__control-button"]')
            await control_buttons.first.wait_for(state='visible', timeout=10000)
            await self._page.wait_for_timeout(1000)
            control_buttons_count = await control_buttons.count()
            logger.info(f'  📊 Found control buttons: {control_buttons_count}')
            
            if control_buttons_count > 0:
                last_control_button = control_buttons.last
                await last_control_button.wait_for(state='visible', timeout=10000)
                await self._page.wait_for_timeout(500)
                logger.info('  🖱️  Clicking last control button...')
                await last_control_button.click()
                logger.info('  ✅ Clicked last control button')
                await self._page.wait_for_timeout(2000)
            else:
                logger.warning('  ⚠️  Control buttons not found')
        
        logger.info(f'🎉 All articles processed successfully! Total: {len(items)}')
        
        # Wait before looking for final buttons
        await self._page.wait_for_timeout(1000)
        
        # After all iterations - find and click second button
        logger.info('🔍 Looking for final control buttons...')
        header_control_buttons_div = self._page.locator('[class^="Recommendation-header__control-buttons"]').first
        await header_control_buttons_div.wait_for(state='visible', timeout=15000)
        await self._page.wait_for_timeout(1000)
        logger.info('✅ Final buttons container found')
        
        buttons = header_control_buttons_div.locator('button')
        buttons_count = await buttons.count()
        logger.info(f'📊 Found buttons in container: {buttons_count}')
        
        if buttons_count >= 2:
            second_button = buttons.nth(1)  # nth(1) = second button (0-indexed)
            await second_button.wait_for(state='visible', timeout=10000)
            await self._page.wait_for_timeout(1000)
            logger.info('🖱️  Clicking second button...')
            await second_button.click()
            await self._page.wait_for_timeout(1000)
            logger.info('✅ Clicked second button')
        else:
            error_msg = f'Error: Expected at least 2 buttons, found: {buttons_count}'
            logger.error(f'❌ {error_msg}')
            raise ValueError(error_msg)

        # --- Stage 4: Запускаем сравнение карточек ---
        await _notify(on_status, 4)
        
        # Wait for comparison data to load
        logger.info('⏳ Waiting for comparison data to load...')
        try:
            # Wait for network activity to settle
            await self._page.wait_for_load_state('networkidle', timeout=20000)
            logger.info('✅ Network idle')
        except PlaywrightTimeoutError:
            logger.warning('⚠️  Network idle timeout, waiting additional time...')
            # If network doesn't become idle, wait at least some time
            await self._page.wait_for_timeout(5000)
        
        # Additional wait for UI to stabilize
        await self._page.wait_for_timeout(1000)
        logger.info('✅ Page stabilized after comparison')
        
        logger.info('✅ compare_cards function completed successfully!')
    
    async def process_filters(
        self,
        on_status: StatusCallback | None = None,
    ) -> tuple[int, int]:
        """
        Process filters and create reports.

        Status stages used: 5 -> 6 -> 7 -> 8 -> 9
        """
        # --- Stage 5: Применяем фильтры отчетов ---
        await _notify(on_status, 5)

        logger.info('🎯 Starting filter processing...')
        
        # Wait for page to stabilize after compare_cards
        logger.info('⏳ Waiting for page to stabilize...')
        try:
            # Wait for network to be idle
            await self._page.wait_for_load_state('networkidle', timeout=20000)
            logger.info('✅ Network is idle')
        except PlaywrightTimeoutError:
            logger.warning('⚠️  Network idle timeout, continuing anyway')
        
        # Additional wait for any loading overlays to disappear
        await self._page.wait_for_timeout(3000)
        logger.info('✅ Page stabilized')
        
        # Counter for processed elements
        processed_count = 0
        
        # Generate unique_id
        unique_id = generate_unique_id(1, 2, 3, 4, 5)
        logger.info(f'🔢 Generated unique_id: {unique_id}')
        
        # Find period filters container
        logger.info('🔍 Looking for period filters...')
        period_filters = self._page.locator('[class^="Period-filters"]').first
        await period_filters.wait_for(state='visible', timeout=20000)
        await self._page.wait_for_timeout(1000)
        logger.info('✅ Period filters found')
        
        # Get all buttons inside first div
        period_buttons = period_filters.locator('> div').first.locator('button')
        period_count = await period_buttons.count()
        logger.info(f'📊 Found {period_count} period buttons')
        
        # Iterate over each period button
        for period_idx in range(period_count):
            # Update status for current period (stages 6-9: Сегодня, Неделя, Месяц, Квартал)
            period_stage = 6 + period_idx
            await _notify(on_status, period_stage)
            
            # Get button text for logging
            period_button = period_buttons.nth(period_idx)
            period_text = await period_button.inner_text()
            logger.info(f'🔘 [{period_idx + 1}/{period_count}] Clicking period button: "{period_text}"')
            
            # Try clicking with retry mechanism
            max_attempts = 3
            for attempt in range(max_attempts):
                try:
                    await period_button.click(timeout=15000)
                    logger.info(f'  ✅ Click successful on attempt {attempt + 1}')
                    break
                except PlaywrightTimeoutError:
                    if attempt < max_attempts - 1:
                        logger.warning(f'  ⚠️  Click attempt {attempt + 1} failed, retrying...')
                        await self._page.wait_for_timeout(2000)
                    else:
                        logger.error(f'  ❌ All {max_attempts} click attempts failed')
                        raise
            
            # Wait after period button click
            await self._page.wait_for_timeout(3000)
            
            # Find params segments container
            logger.info('  🔍 Looking for params segments...')
            params_segments = self._page.locator('[class^="Params-segments"]').first
            await params_segments.wait_for(state='visible', timeout=20000)
            await self._page.wait_for_timeout(2000)
            
            # Get all segment buttons
            segment_buttons = params_segments.locator('> div').first.locator('button')
            segment_count = await segment_buttons.count()
            logger.info(f'  📊 Found {segment_count} segment buttons')
            
            # Iterate over each segment button
            for segment_idx in range(segment_count):
                segment_button = segment_buttons.nth(segment_idx)
                segment_text = await segment_button.inner_text()
                logger.info(f'    🔹 [{segment_idx + 1}/{segment_count}] Clicking segment: "{segment_text}"')
                
                # Try clicking with retry mechanism
                max_attempts = 3
                for attempt in range(max_attempts):
                    try:
                        await segment_button.click(timeout=15000)
                        logger.info(f'      ✅ Click successful on attempt {attempt + 1}')
                        break
                    except PlaywrightTimeoutError:
                        if attempt < max_attempts - 1:
                            logger.warning(f'      ⚠️  Click attempt {attempt + 1} failed, retrying...')
                            await self._page.wait_for_timeout(2000)
                        else:
                            logger.error(f'      ❌ All {max_attempts} click attempts failed')
                            raise
                
                # Wait after segment button click
                await self._page.wait_for_timeout(3000)
                
                try:
                    # Find and click download button
                    logger.info('    💾 Looking for download button...')
                    download_button = self._page.get_by_test_id('Download-manager-open-modal-button-interface')
                    await download_button.wait_for(state='visible', timeout=10000)
                    await self._page.wait_for_timeout(1000)
                    await download_button.click()
                    await self._page.wait_for_timeout(2000)
                    
                    # Process popup
                    logger.info('    📝 Filling popup...')
                    # Find input for filename
                    simple_input = self._page.locator('[class^="Simple-input"]').first
                    await simple_input.wait_for(state='visible', timeout=15000)
                    await self._page.wait_for_timeout(1000)
                    
                    input_field = simple_input.locator('input')
                    await input_field.wait_for(state='visible', timeout=10000)
                    await self._page.wait_for_timeout(500)
                    
                    # Form filename
                    file_name = f'{unique_id}-{period_text}-{segment_text}'
                    logger.info(f'    ⌨️  Entering name: "{file_name}"')
                    await input_field.fill(file_name)
                    await self._page.wait_for_timeout(1000)
                    
                    # Find and click confirmation button
                    logger.info('    🖱️  Clicking confirmation button...')
                    modal = self._page.locator('[class^="Create-excel-modal"]').first
                    await modal.wait_for(state='visible', timeout=15000)
                    await self._page.wait_for_timeout(1000)
                    
                    confirm_button = modal.locator('button').first
                    await confirm_button.wait_for(state='visible', timeout=10000)
                    await self._page.wait_for_timeout(500)
                    await confirm_button.click()
                    await self._page.wait_for_timeout(2000)
                    
                    # Increment counter
                    processed_count += 1
                    logger.info(f'    ✅ Processed: {period_text} -> {segment_text} (total: {processed_count})')
                    
                except PlaywrightTimeoutError:
                    # If download button not found, skip
                    logger.warning(f'    ⚠️  Download button not found for: {period_text} -> {segment_text}, skipping...')
                    continue
        
        logger.info(f'🎉 All filters processed! Processed elements: {processed_count}')
        return unique_id, processed_count
    
    def _merge_zip_archives(self, zip_files: list[str], unique_id: int):
        """Merge multiple zip archives into one with folder organization"""
        if not zip_files:
            logger.warning('⚠️  No files to merge')
            return
        
        logger.info(f'📦 Starting merge of {len(zip_files)} archives...')
        
        # Merged archive name
        merged_zip_path = os.path.join(self._downloads_path, f'{unique_id}-merged.zip')
        
        # Create new zip archive
        with zipfile.ZipFile(merged_zip_path, 'w', zipfile.ZIP_DEFLATED) as merged_zip:
            # Process each zip file
            for zip_path in zip_files:
                # Get filename without extension for folder name
                zip_filename = os.path.basename(zip_path)
                folder_name = os.path.splitext(zip_filename)[0]
                
                # Remove unique_id prefix from folder name if present
                if folder_name.startswith(f'{unique_id}-'):
                    folder_name = folder_name[len(f'{unique_id}-'):]
                
                logger.info(f'  📂 Processing archive: {zip_filename} -> folder: {folder_name}')
                
                try:
                    # Open source zip
                    with zipfile.ZipFile(zip_path, 'r') as source_zip:
                        # Extract each file from archive
                        for file_info in source_zip.infolist():
                            # Skip folders
                            if file_info.is_dir():
                                continue
                            
                            # Read file contents
                            file_data = source_zip.read(file_info.filename)
                            
                            # Create new path with folder
                            new_filename = os.path.join(folder_name, file_info.filename)
                            
                            # Add to merged archive
                            merged_zip.writestr(new_filename, file_data)
                            logger.info(f'    ✅ Added: {new_filename}')
                    
                except Exception as e:
                    logger.error(f'  ❌ Error processing {zip_filename}: {e}')
                    continue
        
        logger.info(f'✅ Merged archive created: {merged_zip_path}')
        
        # Delete source zip files
        logger.info('🗑️  Deleting source archives...')
        for zip_path in zip_files:
            try:
                os.unlink(zip_path)
                logger.info(f'  🗑️  Deleted: {os.path.basename(zip_path)}')
            except Exception as e:
                logger.warning(f'  ⚠️  Error deleting {zip_path}: {e}')
        
        logger.info('🎉 Archive merge completed!')
        
        return merged_zip_path
    
    async def download_documents(
        self,
        unique_id: int,
        expected_count: int,
        on_status: StatusCallback | None = None,
    ) -> str:
        """
        Download created documents and return path to merged ZIP.

        Status stages used: 10 -> 11 -> 12 -> 13
        """
        # --- Stage 10: Открываем менеджер загрузок ---
        await _notify(on_status, 10)

        logger.info(f'📥 Starting document download (expected: {expected_count})...')
        
        # Create downloads folder if it doesn't exist
        if not os.path.exists(self._downloads_path):
            os.makedirs(self._downloads_path)
            logger.info(f'📁 Created folder: {self._downloads_path}')
        
        # Create unique folder for this download session
        unique_folder = os.path.join(self._downloads_path, str(unique_id))
        if os.path.exists(unique_folder):
            logger.info(f'🗑️  Removing existing folder: {unique_folder}')
            shutil.rmtree(unique_folder)
        os.makedirs(unique_folder)
        logger.info(f'📁 Created unique folder: {unique_folder}')
        
        # Find and click show downloads list button
        logger.info('🔍 Looking for downloads list button...')
        show_list_button = self._page.get_by_test_id('Download-manager-wrapper-show-list-button-interface')
        await show_list_button.wait_for(state='visible', timeout=20000)
        await self._page.wait_for_timeout(2000)
        await show_list_button.click()
        await self._page.wait_for_timeout(3000)
        logger.info('✅ Downloads list opened')

        # --- Stage 11: Ожидаем готовности документов ---
        await _notify(on_status, 11)
        
        # Wait for full list loading
        logger.info('⏳ Waiting for full document list loading...')
        
        # Find all buttons with data-testid="File-row-SUCCESS-chips-component"
        logger.info('🔍 Looking for all buttons with data-testid="File-row-SUCCESS-chips-component"...')
        chip_buttons = self._page.locator('button[data-testid="File-row-SUCCESS-chips-component"]')
        
        # Wait for at least one element (up to 90 seconds)
        await chip_buttons.first.wait_for(state='visible', timeout=90000)
        logger.info('✅ Elements appeared on page')
        
        # Additionally wait for element count stabilization
        await self._page.wait_for_timeout(5000)
        
        buttons_count = await chip_buttons.count()
        logger.info(f'📊 Found buttons: {buttons_count}')

        # --- Stage 12: Скачиваем документы ---
        await _notify(on_status, 12)
        
        # Determine how many files to download
        files_to_download = min(buttons_count, expected_count)
        logger.info(f'📥 Will download files: {files_to_download}')
        
        # Download files
        downloaded_count = 0
        downloaded_files = []  # List of downloaded file paths
        
        for idx in range(files_to_download):
            logger.info(f'  💾 [{idx + 1}/{files_to_download}] Downloading file...')
            
            try:
                # Get button by index
                button = chip_buttons.nth(idx)
                
                # Explicitly scroll to element before clicking
                logger.info('    📜 Scrolling to button...')
                await button.scroll_into_view_if_needed()
                await self._page.wait_for_timeout(2000)  # Wait after scroll
                logger.info('    ✅ Scrolled to button')
                
                # Wait for button to be ready
                await button.wait_for(state='visible', timeout=10000)
                await self._page.wait_for_timeout(1000)
                
                # Wait for download start
                async with self._page.expect_download(timeout=45000) as download_info:
                    await button.click()
                    logger.info('    🖱️  Button clicked')
                
                download = await download_info.value
                
                # Get filename
                suggested_filename = download.suggested_filename
                logger.info(f'    📄 Filename: "{suggested_filename}"')
                
                # Save file to unique folder
                download_path = os.path.join(unique_folder, suggested_filename)
                await download.save_as(download_path)
                downloaded_files.append(download_path)
                downloaded_count += 1
                logger.info(f'    ✅ Saved: {download_path}')
                
                # Wait between downloads
                await self._page.wait_for_timeout(2000)
                    
            except Exception as e:
                logger.warning(f'    ⚠️  Error downloading file: {e}')
                import traceback
                logger.debug(f'    📋 Traceback: {traceback.format_exc()}')
        
        logger.info(f'🎉 Download completed! Downloaded documents: {downloaded_count}')

        # --- Stage 13: Упаковываем архив ---
        await _notify(on_status, 13)
        
        # Merge all downloaded zip archives into one
        if downloaded_files:
            merged_path = self._merge_zip_archives(downloaded_files, unique_id)
            
            # Delete the unique folder after merging
            logger.info(f'🗑️  Removing temporary folder: {unique_folder}')
            shutil.rmtree(unique_folder)
            logger.info('✅ Temporary folder removed')
            
            return merged_path
        
        raise Exception("No files were downloaded")
