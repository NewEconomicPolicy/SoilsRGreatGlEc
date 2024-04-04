
        # create data frame from main data set
        # ====================================
        inp_fname = 'HWSD_DATA.csv'
        csv_file = os.path.join(self.hwsd_dir, inp_fname)
        if not os.path.exists(csv_file):
            sys.stdout.write('Error in  get_soil_recs file does not exist: ' + csv_file + ' cannot proceed \n')
            return None

        data_frame = read_csv(csv_file)




this_time = ()
    nrows_read = hwsd.read_bbox_mu_globals(form.setup['bbox'])  # create grid of MU_GLOBAL values
    new_time = time()
    print('Read {} rows from HWSD .bil file in {} seconds'.format(nrows_read, round(new_time - this_time)))
    this_time = new_time
    mu_globals = hwsd.get_mu_globals_dict()             # retrieve dictionary of mu_globals and number of occurrences
    soil_recs  = hwsd.get_soil_recs(sorted(mu_globals.keys(), reverse=True))
    print('Generated {} soil recordsin {} seconds'.format(len(soil_recs), round(new_time - this_time)))
    return